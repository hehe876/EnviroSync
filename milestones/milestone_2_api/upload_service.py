"""Allowlisted, immutable S3 uploads with independent regional registry objects.

Never overwrites or alters the original Chennai/London ERA5 catalog or datasets.
"""
import base64
import binascii
import csv
from datetime import date, timedelta, datetime, timezone
from hashlib import sha256
import io
import json
import math
import re

from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

from milestones.milestone_1b_federation.common import to_json_bytes
from .errors import ApiProblem

PREFIX = "envirosync/v1/uploads"
REGISTRY_PREFIX = f"{PREFIX}/manifests/"
DATA_PREFIX = f"{PREFIX}/datasets/"
MAX_UPLOAD_BYTES = 200_000
MAX_OBSERVATIONS = 366
MAX_ADDITIONAL_DATASETS = 20
CITY_RE = re.compile(r"[a-z][a-z0-9-]{2,29}\Z")
VALID_REGIONS = {"ap-south-1", "eu-west-2"}
METRIC_KEYS = ("max_temp_c", "min_temp_c", "precipitation_mm")


class UploadRequest(BaseModel):
    city: str = Field(min_length=3, max_length=30)
    country: str = Field(min_length=2, max_length=60)
    region: str
    source: str = Field(min_length=2, max_length=120)
    filename: str = Field(min_length=5, max_length=120)
    file_base64: str = Field(min_length=4, max_length=280_000)


def parse_upload(payload):
    if not CITY_RE.fullmatch(payload.city) or payload.city in {"chennai", "london"}:
        raise ApiProblem(400, "INVALID_CITY", "Use a new lowercase city ID (3–30 letters, numbers or hyphens).")
    if payload.region not in VALID_REGIONS:
        raise ApiProblem(400, "INVALID_REGION", "Choose ap-south-1 or eu-west-2.")
    if not re.fullmatch(r"[\w .(),'/-]{2,60}", payload.country, re.ASCII):
        raise ApiProblem(400, "INVALID_COUNTRY", "Country contains unsupported characters.")
    if not re.fullmatch(r"[\w .(),'/-]{2,120}", payload.source, re.ASCII):
        raise ApiProblem(400, "INVALID_SOURCE", "Source contains unsupported characters.")
    filename = payload.filename.lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,118}\.(csv|json)", filename):
        raise ApiProblem(400, "INVALID_FILENAME", "Choose a CSV or JSON file with a simple filename.")
    if len(payload.file_base64) > 280_000:
        raise ApiProblem(413, "FILE_TOO_LARGE", "Maximum raw upload size is 200 KB.")
    try:
        raw = base64.b64decode(payload.file_base64, validate=True)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise ApiProblem(413, "FILE_TOO_LARGE", "Maximum raw upload size is 200 KB.")
        content = raw.decode("utf-8-sig")
    except (binascii.Error, UnicodeError) as exc:
        raise ApiProblem(400, "INVALID_FILE", "File must be valid UTF-8 CSV or JSON.") from exc
    if filename.endswith(".csv"):
        try:
            reader = csv.DictReader(io.StringIO(content, newline=""), strict=True)
            fieldnames = reader.fieldnames or []
            allowed = ["date", "temp_max_c", "temp_min_c", "precipitation_mm"]
            if fieldnames != allowed:
                raise ApiProblem(400, "INVALID_COLUMNS", "CSV columns must be date,temp_max_c,temp_min_c,precipitation_mm.")
            rows = list(reader)
            if any(None in row or None in row.values() for row in rows):
                raise ApiProblem(400, "INVALID_CSV", "CSV rows have missing or extra columns.")
        except (csv.Error, UnicodeError) as exc:
            raise ApiProblem(400, "INVALID_CSV", "CSV data is malformed.") from exc
    else:
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ApiProblem(400, "INVALID_JSON", "Invalid JSON file.") from exc
        rows = decoded.get("observations") if isinstance(decoded, dict) else decoded
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_OBSERVATIONS:
        raise ApiProblem(400, "INVALID_ROWS", "Provide 1–366 daily observations.")
    normalized = []
    for item in rows:
        if not isinstance(item, dict):
            raise ApiProblem(400, "INVALID_ROWS", "Each observation must be an object.")
        try:
            day = str(item["date"])
            day_value = date.fromisoformat(day)
            if day_value.isoformat() != day:
                raise ValueError("Invalid date format")
            # Accept either canonical S3 field names or dashboard API field names.
            maximum = float(item.get("temp_max_c", item.get("max_temp_c")))
            minimum = float(item.get("temp_min_c", item.get("min_temp_c")))
            precipitation = float(item["precipitation_mm"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ApiProblem(400, "INVALID_ROWS", "Every row needs ISO date, max/min °C and rainfall in mm.") from exc
        if not all(map(math.isfinite, (maximum, minimum, precipitation))):
            raise ApiProblem(400, "INVALID_VALUES", "Readings must be finite numbers.")
        if maximum < minimum or precipitation < 0 or not (-100 <= minimum <= 80 and -100 <= maximum <= 80) or precipitation > 5000:
            raise ApiProblem(400, "INVALID_VALUES", "Temperature or precipitation values are inconsistent.")
        if normalized and day_value != date.fromisoformat(normalized[-1]["date"]) + timedelta(days=1):
            raise ApiProblem(400, "MISSING_DATES", "Dates must be ordered and consecutive, without duplicates.")
        normalized.append({"date": day, "max_temp_c": maximum, "min_temp_c": minimum, "precipitation_mm": precipitation})
    return normalized


class UploadService:
    def __init__(self, federation):
        self.federation = federation
        self.settings = federation.settings
        self.store = federation.store

    def bucket_for(self, region):
        if region == "ap-south-1":
            return self.settings.city("chennai").bucket
        if region == "eu-west-2":
            return self.settings.city("london").bucket
        raise ApiProblem(400, "INVALID_REGION", "Unsupported AWS region.")

    def list_entries(self):
        bucket = self.settings.catalog_bucket
        region = self.settings.catalog_region
        response = self.store.client(region).list_objects_v2(
            Bucket=bucket,
            Prefix=REGISTRY_PREFIX,
            MaxKeys=MAX_ADDITIONAL_DATASETS + 1,
        )
        objects = response.get("Contents", [])
        if response.get("IsTruncated") or len(objects) > MAX_ADDITIONAL_DATASETS:
            raise ValueError("Uploaded dataset limit exceeded; administrator review required")
        entries = []
        seen = set()
        for item in objects:
            key = item["Key"]
            match = re.fullmatch(re.escape(REGISTRY_PREFIX) + r"([a-z][a-z0-9-]{2,29})\.json", key)
            if not match:
                raise ValueError("Unexpected uploaded registry object")
            raw = self.store.get_bytes(region, bucket, key)
            try:
                entry = json.loads(raw)
            except (UnicodeError, ValueError) as exc:
                raise ValueError("Uploaded registry JSON is invalid") from exc
            city = match.group(1)
            if not isinstance(entry, dict) or entry.get("city") != city or city in seen or city in self.settings.cities:
                raise ValueError("Uploaded registry has invalid or duplicate city")
            if entry.get("region") not in VALID_REGIONS:
                raise ValueError("Uploaded registry contains unsupported region")
            if entry.get("bucket") != self.bucket_for(entry["region"]) or entry.get("key") != f"{DATA_PREFIX}{city}.json":
                raise ValueError("Uploaded registry contains unexpected S3 pointer")
            if entry.get("dataset_id") != f"{city}-daily-weather-uploaded":
                raise ValueError("Uploaded registry contains incorrect dataset identifier")
            digest = entry.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
                raise ValueError("Uploaded registry contains invalid SHA-256")
            for field in ("country", "source", "start_date", "end_date", "observation_count"):
                if field not in entry:
                    raise ValueError("Uploaded registry is missing required metadata")
            seen.add(city)
            entries.append(entry)
        return sorted(entries, key=lambda item: item["city"])

    def publish(self, payload, uploader):
        observations = parse_upload(payload)
        existing = self.list_entries()
        if len(existing) >= MAX_ADDITIONAL_DATASETS:
            raise ApiProblem(409, "DATASET_LIMIT", "Maximum 20 administrator-uploaded datasets reached.")
        if payload.city in {item["city"] for item in existing}:
            raise ApiProblem(409, "DATASET_EXISTS", "A dataset for this city already exists.")
        bucket = self.bucket_for(payload.region)
        key = f"{DATA_PREFIX}{payload.city}.json"
        first, last = observations[0]["date"], observations[-1]["date"]
        data = {
            "schema_version": "1.0",
            "dataset_id": f"{payload.city}-daily-weather-uploaded",
            "city": payload.city,
            "country": payload.country,
            "start_date": first,
            "end_date": last,
            "observation_count": len(observations),
            "source": {"provider": payload.source, "dataset": "Administrator-uploaded historical daily readings", "attribution": "Uploaded by an authorized EnviroSync administrator", "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")},
            "observations": observations,
        }
        raw = to_json_bytes(data)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise ApiProblem(413, "FILE_TOO_LARGE", "Normalized dataset exceeds the upload size limit.")
        entry = {
            "dataset_id": data["dataset_id"], "city": payload.city,
            "country": payload.country, "region": payload.region,
            "bucket": bucket, "key": key, "source": payload.source,
            "start_date": first, "end_date": last,
            "observation_count": len(observations), "timezone": "UTC",
            "sha256": sha256(raw).hexdigest(), "size_bytes": len(raw),
        }
        # S3 conditional writes prevent overwriting existing objects.
        try:
            self.store.client(payload.region).put_object(
                Bucket=bucket, Key=key, Body=raw,
                IfNoneMatch="*", ContentType="application/json",
                ServerSideEncryption="AES256",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"PreconditionFailed", "ConditionalRequestConflict"}:
                raise ApiProblem(409, "DATASET_EXISTS", "Uploaded dataset already exists.") from exc
            raise
        manifest_key = f"{REGISTRY_PREFIX}{payload.city}.json"
        try:
            self.store.client(self.settings.catalog_region).put_object(
                Bucket=self.settings.catalog_bucket, Key=manifest_key,
                Body=to_json_bytes(entry), IfNoneMatch="*",
                ContentType="application/json", ServerSideEncryption="AES256",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"PreconditionFailed", "ConditionalRequestConflict"}:
                raise ApiProblem(409, "DATASET_EXISTS", "Uploaded registry entry already exists.") from exc
            raise
        return entry

    def retrieve(self, entry, start, end):
        raw = self.store.get_bytes(entry["region"], entry["bucket"], entry["key"])
        if sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("Uploaded dataset SHA-256 integrity check failed")
        try:
            data = json.loads(raw)
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Uploaded dataset JSON is malformed") from exc
        if not isinstance(data, dict) or data.get("city") != entry["city"] or data.get("dataset_id") != entry["dataset_id"]:
            raise ValueError("Uploaded data identity is inconsistent")
        rows = data.get("observations")
        if not isinstance(rows, list) or len(rows) != entry["observation_count"]:
            raise ValueError("Uploaded data observation count is inconsistent")
        if not rows or rows[0].get("date") != entry["start_date"] or rows[-1].get("date") != entry["end_date"]:
            raise ValueError("Uploaded data date range is inconsistent")
        # Validate the S3 object again, not just on initial upload.
        raw_rows = [{"date": r.get("date"), "temp_max_c": r.get("max_temp_c"), "temp_min_c": r.get("min_temp_c"), "precipitation_mm": r.get("precipitation_mm")} for r in rows]
        encoded = base64.b64encode(json.dumps(raw_rows).encode()).decode()
        parsed = parse_upload(UploadRequest(city=entry["city"], country=entry["country"], region=entry["region"], source=entry["source"], filename="verify.json", file_base64=encoded))
        if parsed != rows:
            raise ValueError("Uploaded data content does not match validated observations")
        return {
            "city": entry["city"], "region": entry["region"],
            "source": data["source"], "start_date": entry["start_date"],
            "end_date": entry["end_date"],
            "observations": [row for row in rows if start <= row["date"] <= end],
            "sha256_verified": True,
        }
