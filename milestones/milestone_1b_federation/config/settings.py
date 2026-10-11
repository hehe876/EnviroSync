"""Validate environment configuration and define the two supported regional datasets."""

from dataclasses import dataclass
from pathlib import Path
import os
import re

from dotenv import load_dotenv

PREFIX = "envirosync/v1"
CATALOG_KEY = f"{PREFIX}/catalog/datasets.json"
MAX_JSON_BYTES = 2_000_000


@dataclass(frozen=True)
class City:
    name: str
    country: str
    latitude: float
    longitude: float
    timezone: str
    region: str
    bucket: str

    @property
    def key(self):
        return f"{PREFIX}/datasets/{self.name}-daily-weather.json"


class Settings:
    def __init__(self, env_path=".env"):
        load_dotenv(dotenv_path=Path(env_path), override=False)
        india = os.getenv("INDIA_BUCKET", "").strip()
        london = os.getenv("LONDON_BUCKET", "").strip()
        india_region = os.getenv("INDIA_REGION", "").strip()
        london_region = os.getenv("LONDON_REGION", "").strip()

        if india_region != "ap-south-1" or london_region != "eu-west-2":
            raise ValueError(".env must define INDIA_REGION=ap-south-1 and LONDON_REGION=eu-west-2")
        for bucket in (india, london):
            if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
                raise ValueError("INDIA_BUCKET and LONDON_BUCKET must be valid nonempty S3 bucket names")
        if india == london:
            raise ValueError("India and London must use separate S3 buckets")

        self.cities = {
            "chennai": City("chennai", "India", 13.0827, 80.2707, "Asia/Kolkata", india_region, india),
            "london": City("london", "United Kingdom", 51.5074, -0.1278, "Europe/London", london_region, london),
        }
        self.catalog_bucket = india
        self.catalog_region = india_region

    def city(self, name):
        city = self.cities.get(name.lower())
        if city is None:
            raise ValueError(f"Unsupported city '{name}'. Choose chennai or london.")
        return city
