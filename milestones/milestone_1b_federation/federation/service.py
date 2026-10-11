"""End-to-end regional publication, authenticated discovery and SHA-256 retrieval."""
from datetime import date
from hashlib import sha256
import json
from milestones.milestone_1b_federation.config import CATALOG_KEY
from milestones.milestone_1b_federation.ingestion import validate_dataset
from milestones.milestone_1b_federation.storage import S3ObjectStore
from milestones.milestone_1b_federation.common import to_json_bytes
from milestones.milestone_1b_federation.catalog import CatalogService

class S3Federation:
    """Application service; depends on storage/catalog contracts, not FastAPI."""
    def __init__(self, settings, session=None, store=None):
        self.settings = settings
        self.store = store if store is not None else S3ObjectStore(session=session)
        self.catalog = CatalogService(settings, self.store)

    def discover(self):
        return self.catalog.discover()

    def publish(self, datasets):
        expected = set(self.settings.cities)
        if set(datasets) != expected:
            raise ValueError("Publishing requires both Chennai and London datasets")
        for name, city in self.settings.cities.items():
            validate_dataset(datasets[name], city)
            self.store.verify_region(city.bucket, city.region)
        self.store.verify_region(self.settings.catalog_bucket, self.settings.catalog_region)

        entries = []
        for name, city in self.settings.cities.items():
            data = datasets[name]
            raw = to_json_bytes(data)
            self.store.put_bytes(city.region, city.bucket, city.key, raw)
            entries.append({
                "dataset_id": data["dataset_id"],
                "city": city.name,
                "country": city.country,
                "region": city.region,
                "bucket": city.bucket,
                "key": city.key,
                "start_date": data["start_date"],
                "end_date": data["end_date"],
                "observation_count": data["observation_count"],
                "timezone": city.timezone,
                "source": data["source"]["provider"],
                "sha256": sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            })
        return self.catalog.publish_manifest(entries)

    def retrieve(self, city_name, start=None, end=None):
        city = self.settings.city(city_name)
        catalog = self.discover()
        entry = next(e for e in catalog["datasets"] if e["city"] == city.name)
        raw = self.store.get_bytes(entry["region"], entry["bucket"], entry["key"])
        if sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"S3 content integrity check failed for {city.name}")
        try:
            data = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Regional dataset is not valid JSON") from exc
        validate_dataset(data, city)
        if (entry["start_date"], entry["end_date"], entry["observation_count"]) != (data["start_date"], data["end_date"], data["observation_count"]):
            raise ValueError("Catalog metadata does not match the regional dataset")
        for label, value in (("Start", start), ("End", end)):
            if value is not None:
                try:
                    if len(value) != 10 or date.fromisoformat(value).isoformat() != value:
                        raise ValueError()
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{label} date must use a valid YYYY-MM-DD date") from exc
        if start is not None and start < data["start_date"]:
            raise ValueError(f"Start date must be on or after {data['start_date']}")
        if end is not None and end > data["end_date"]:
            raise ValueError(f"End date must be on or before {data['end_date']}")
        if start and end and start > end:
            raise ValueError("Start date cannot be after end date")
        readings = [row for row in data["observations"] if (start is None or row["date"] >= start) and (end is None or row["date"] <= end)]
        return {"city": city.name, "region": city.region, "bucket": city.bucket,
                "source": data["source"], "start_date": data["start_date"],
                "end_date": data["end_date"], "total_records": len(readings),
                "observations": readings, "sha256_verified": True}
