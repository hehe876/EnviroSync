import json

import pytest

from milestones.milestone_1b_federation.federation import S3Federation
from milestones.milestone_1b_federation.config import CATALOG_KEY
from milestones.milestone_1b_federation.ingestion import normalize_weather
from conftest import sample_api_payload


def make_datasets(settings):
    output = {}
    for name, city in settings.cities.items():
        payload = sample_api_payload(timezone=city.timezone)
        output[name] = normalize_weather(city, "2025-07-01", "2025-07-03", payload, "https://example.invalid/test")
    return output


def test_publish_and_retrieve_from_distinct_regions(settings, fake_session):
    store = S3Federation(settings, session=fake_session)
    catalog = store.publish(make_datasets(settings))
    assert catalog["datasets"][0]["region"] == "ap-south-1"
    assert catalog["datasets"][1]["region"] == "eu-west-2"
    assert ("ap-south-1", settings.catalog_bucket, CATALOG_KEY) in fake_session.objects
    assert store.retrieve("london")["total_records"] == 3
    assert store.retrieve("chennai")["sha256_verified"] is True
    assert set(fake_session.regions) == {"ap-south-1", "eu-west-2"}


def test_filter_returns_only_matching_days(settings, fake_session):
    store = S3Federation(settings, session=fake_session)
    store.publish(make_datasets(settings))
    results = store.retrieve("london", start="2025-07-02", end="2025-07-02")
    assert results["total_records"] == 1
    assert results["observations"][0]["date"] == "2025-07-02"


def test_reject_corrupted_regional_object(settings, fake_session):
    store = S3Federation(settings, session=fake_session)
    store.publish(make_datasets(settings))
    city = settings.city("london")
    key = (city.region, city.bucket, city.key)
    data = json.loads(fake_session.objects[key])
    data["observations"][0]["max_temp_c"] = 999
    fake_session.objects[key] = json.dumps(data).encode("utf-8")
    with pytest.raises(ValueError, match="integrity"):
        store.retrieve("london")


def test_reject_unapproved_catalog_pointer(settings, fake_session):
    store = S3Federation(settings, session=fake_session)
    store.publish(make_datasets(settings))
    key = (settings.catalog_region, settings.catalog_bucket, CATALOG_KEY)
    catalog = json.loads(fake_session.objects[key])
    catalog["datasets"][1]["bucket"] = "unexpected-bucket"
    fake_session.objects[key] = json.dumps(catalog).encode("utf-8")
    with pytest.raises(ValueError, match="unexpected region"):
        store.discover()


def test_reject_unknown_city(settings, fake_session):
    store = S3Federation(settings, session=fake_session)
    with pytest.raises(ValueError, match="Unsupported city"):
        store.retrieve("paris")
