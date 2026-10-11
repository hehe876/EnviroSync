"""Published global catalog validation and discovery.

Catalog pointers are always checked against the allowlisted configuration:
remote S3 data cannot choose arbitrary buckets, regions or object keys.
"""
from datetime import datetime, timezone
import json
from milestones.milestone_1b_federation.config import CATALOG_KEY
from milestones.milestone_1b_federation.common import to_json_bytes

class CatalogService:
    def __init__(self, settings, store):
        self.settings = settings
        self.store = store

    def publish_manifest(self, entries):
        catalog = {
            "schema_version": "1.0",
            "project": "EnviroSync Federation",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "datasets": entries,
        }
        self.store.put_bytes(self.settings.catalog_region, self.settings.catalog_bucket,
                             CATALOG_KEY, to_json_bytes(catalog))
        return catalog

    def discover(self):
        raw = self.store.get_bytes(self.settings.catalog_region, self.settings.catalog_bucket, CATALOG_KEY)
        try:
            catalog = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Catalog is not valid JSON") from exc
        if not isinstance(catalog, dict) or catalog.get("schema_version") != "1.0":
            raise ValueError("Unrecognized S3 catalog format")
        entries = catalog.get("datasets")
        if not isinstance(entries, list) or len(entries) != len(self.settings.cities):
            raise ValueError("Catalog must contain exactly the supported two datasets")
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("city") not in self.settings.cities:
                raise ValueError("Catalog has an unsupported dataset")
            city = self.settings.city(entry["city"])
            if city.name in seen:
                raise ValueError("Catalog contains duplicate entries")
            seen.add(city.name)
            if (entry.get("region"), entry.get("bucket"), entry.get("key")) != (city.region, city.bucket, city.key):
                raise ValueError("Catalog entry points to an unexpected region, bucket or key")
            if entry.get("dataset_id") != f"{city.name}-daily-weather-era5":
                raise ValueError("Catalog dataset_id is invalid")
            digest = entry.get("sha256")
            if not isinstance(digest, str) or len(digest) != 64 or any(x not in "0123456789abcdef" for x in digest):
                raise ValueError("Catalog entry has an invalid sha256")
        return catalog

