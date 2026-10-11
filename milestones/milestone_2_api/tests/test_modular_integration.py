"""Milestone 1B <-> 2 integration with explicit missing-component negative controls.

No HTTP, S3, AWS credentials, or remote data calls leave this process.
"""
from fastapi.testclient import TestClient
from milestones.milestone_1b_federation.config import CATALOG_KEY
from milestones.milestone_2_api import app, get_federation
from milestones.milestone_1b_federation.federation import S3Federation
from milestones.milestone_1b_federation.ingestion import normalize_weather
from conftest import sample_api_payload


def test_api_cannot_claim_catalog_without_milestone_1b(settings, fake_session):
    """Negative control: health alone does NOT prove milestone 1B exists."""
    federation = S3Federation(settings, session=fake_session)
    app.dependency_overrides[get_federation] = lambda: federation
    try:
        with TestClient(app) as client:
            assert client.get("/api/health").status_code == 200
            response = client.get("/api/datasets")
        assert response.status_code == 502
        assert response.json()["error"]["code"] == "INVALID_REMOTE_DATA"
    finally:
        app.dependency_overrides.clear()


def test_full_flow_requires_both_regions_and_sha256(settings, fake_session):
    """Ingestion->regional S3->catalog->HTTP must work; remove 1B data -> 502."""
    federation = S3Federation(settings, session=fake_session)
    prepared = {}
    for name, city in settings.cities.items():
        prepared[name] = normalize_weather(
            city, "2025-07-01", "2025-07-03",
            sample_api_payload(timezone=city.timezone), "https://example.invalid/fixture"
        )
    federation.publish(prepared)
    app.dependency_overrides[get_federation] = lambda: federation
    try:
        with TestClient(app) as client:
            normal = client.get("/api/compare", params={
                "city1": "chennai", "city2": "london", "start": "2025-07-01",
                "end": "2025-07-03", "metric": "temp_max_c"
            })
            assert normal.status_code == 200
            assert len(normal.json()["points"]) == 3
            assert normal.json()["sources"]["london"]["sha256_verified"] is True

            london = settings.city("london")
            regional_pointer = (london.region, london.bucket, london.key)
            fake_session.objects.pop(regional_pointer)
            missing = client.get("/api/compare", params={
                "city1": "chennai", "city2": "london", "start": "2025-07-01",
                "end": "2025-07-03", "metric": "temp_max_c"
            })
            assert missing.status_code == 502
            assert missing.json()["error"]["code"] == "INVALID_REMOTE_DATA"
            federation.publish(prepared)
            restored = client.get("/api/compare", params={
                "city1": "chennai", "city2": "london", "start": "2025-07-01",
                "end": "2025-07-03", "metric": "temp_max_c"
            })
            assert restored.status_code == 200
            assert set(fake_session.regions) == {"ap-south-1", "eu-west-2"}
    finally:
        app.dependency_overrides.clear()


def test_catalog_is_an_actual_dependency(settings, fake_session):
    """Removing the catalog must break discovery, not trigger a fabricated response."""
    federation = S3Federation(settings, session=fake_session)
    datasets = {
        name: normalize_weather(city, "2025-07-01", "2025-07-03",
          sample_api_payload(timezone=city.timezone), "https://example.invalid/fixture")
        for name, city in settings.cities.items()
    }
    federation.publish(datasets)
    fake_session.objects.pop((settings.catalog_region, settings.catalog_bucket, CATALOG_KEY))
    app.dependency_overrides[get_federation] = lambda: federation
    try:
        with TestClient(app) as client:
            result = client.get("/api/datasets")
        assert result.status_code == 502
    finally:
        app.dependency_overrides.clear()
