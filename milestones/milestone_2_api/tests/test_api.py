"""End-to-end HTTP tests with a fake in-memory S3 session (never uses AWS)."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from milestones.milestone_2_api import app, get_federation
from milestones.milestone_1b_federation.federation import S3Federation
from milestones.milestone_1b_federation.ingestion import normalize_weather
from conftest import sample_api_payload


@pytest.fixture
def web_client(settings, fake_session):
    federation = S3Federation(settings, session=fake_session)
    datasets = {}
    for name, city in settings.cities.items():
        payload = sample_api_payload(first="2025-07-01", n=3, timezone=city.timezone)
        datasets[name] = normalize_weather(city, "2025-07-01", "2025-07-03", payload, "https://example.invalid/test")
    federation.publish(datasets)
    app.dependency_overrides[get_federation] = lambda: federation
    with TestClient(app) as client:
        yield client, federation, fake_session
    app.dependency_overrides.clear()


def test_health_makes_no_aws_call(settings, fake_session):
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "envirosync-api", "aws_checked": False}
    assert fake_session.regions == []


def test_datasets_contract_and_private_bucket_not_leaked(web_client):
    client, store, _ = web_client
    response = client.get("/api/datasets")
    assert response.status_code == 200
    data = response.json()
    assert [row["city"] for row in data["datasets"]] == ["chennai", "london"]
    assert [row["aws_region"] for row in data["datasets"]] == ["ap-south-1", "eu-west-2"]
    assert "temp_max_c" in data["datasets"][0]["variables"]
    assert "bucket" not in data["datasets"][0]


def test_observations_live_from_london_fake_region(web_client):
    client, store, session = web_client
    response = client.get("/api/observations", params={"city":"london", "start":"2025-07-02", "end":"2025-07-03"})
    assert response.status_code == 200
    result = response.json()
    assert result["aws_region"] == "eu-west-2"
    assert result["sha256_verified"] is True
    assert result["row_count"] == 2
    assert result["rows"][0] == {"date": "2025-07-02", "temp_max_c": 31.0, "temp_min_c": 21.0, "precipitation_mm": 1.0}
    assert set(session.regions) == {"ap-south-1", "eu-west-2"}


def test_compare_aligned_temperatures(web_client):
    client, _, _ = web_client
    r=client.get("/api/compare",params={"city1":"chennai","city2":"london","start":"2025-07-01","end":"2025-07-03","metric":"temp_max_c"})
    assert r.status_code == 200
    data = r.json()
    assert data["unit"] == "°C"
    assert data["points"][1] == {"date":"2025-07-02","chennai":31.0,"london":31.0}
    assert data["sources"]["london"]["sha256_verified"] is True


def test_compare_precipitation(web_client):
    client, _, _ = web_client
    data = client.get("/api/compare", params={"city1":"london","city2":"chennai","start":"2025-07-01","end":"2025-07-02","metric":"precipitation_mm"}).json()
    assert data["unit"] == "mm"
    assert data["points"][1]["chennai"] == 1.0


@pytest.mark.parametrize("params,code", [
    ({"city":"paris","start":"2025-07-01","end":"2025-07-02"},"DATASET_NOT_FOUND"),
    ({"city":"london","start":"2025-07-03","end":"2025-07-01"},"INVALID_DATE_RANGE"),
    ({"city":"london","start":"2025-13-01","end":"2025-07-03"},"INVALID_DATE"),
    ({"city":"london","start":"2025-06-30","end":"2025-07-03"},"OUTSIDE_DATASET_COVERAGE"),
    ({"city":"london","start":"2025-07-01","end":"2025-08-01"},"DATE_RANGE_TOO_LARGE"),
])
def test_observation_errors(web_client, params, code):
    client, _, _ = web_client
    resp = client.get("/api/observations", params=params)
    assert resp.status_code in (400, 404)
    assert resp.json()["error"]["code"] == code


def test_required_query_parameter(web_client):
    client, _, _ = web_client
    response = client.get("/api/observations", params={"city":"london"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_QUERY"


def test_compare_rejects_same_city(web_client):
    client, _, _ = web_client
    response=client.get("/api/compare", params={"city1":"london","city2":"london","start":"2025-07-01","end":"2025-07-02"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DUPLICATE_CITIES"


def test_compare_rejects_unknown_metric(web_client):
    client, _, _ = web_client
    response=client.get("/api/compare", params={"city1":"london","city2":"chennai","start":"2025-07-01","end":"2025-07-02","metric":"wind_speed"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNKNOWN_METRIC"


def test_cors_allows_local_vite_only(web_client):
    client, _, _ = web_client
    accepted=client.get("/api/health",headers={"Origin":"http://127.0.0.1:5173"})
    declined=client.get("/api/health",headers={"Origin":"https://example.org"})
    assert accepted.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert "access-control-allow-origin" not in declined.headers


def test_prediction_not_fabricated(web_client):
    client, _, _ = web_client
    response = client.get("/api/predict")
    assert response.status_code == 404


def test_catalog_forgery_rejected_as_bad_remote_data(web_client):
    client, store, session = web_client
    from milestones.milestone_1b_federation.config import CATALOG_KEY
    import json
    obj_key=(store.settings.catalog_region, store.settings.catalog_bucket, CATALOG_KEY)
    catalog=json.loads(session.objects[obj_key])
    catalog["datasets"][0]["bucket"]="unauthorized-bucket"
    session.objects[obj_key]=json.dumps(catalog).encode()
    response=client.get("/api/datasets")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "INVALID_REMOTE_DATA"
    assert "unauthorized-bucket" not in response.text


def test_tampered_dataset_rejected(web_client):
    client, store, session = web_client
    import json
    city=store.settings.city("london")
    key=(city.region,city.bucket,city.key)
    obj=json.loads(session.objects[key])
    obj["observations"][0]["max_temp_c"]=77.7
    session.objects[key]=json.dumps(obj).encode()
    response=client.get("/api/observations",params={"city":"london","start":"2025-07-01","end":"2025-07-03"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "INVALID_REMOTE_DATA"
