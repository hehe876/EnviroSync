"""M4C administrator upload end-to-end tests. No real AWS calls."""
import base64
import json
from datetime import date, timedelta
from hashlib import sha256
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from conftest import FakeS3, FakeSession, sample_api_payload
from milestones.milestone_1b_federation.federation import S3Federation
from milestones.milestone_1b_federation.ingestion import normalize_weather
from milestones.milestone_2_api import app, get_federation
from milestones.milestone_2_api.admin_auth import require_admin
from milestones.milestone_2_api.upload_service import UploadService, REGISTRY_PREFIX, DATA_PREFIX


class UploadFakeS3(FakeS3):
    def put_object(self, Bucket, Key, Body, ContentType, ServerSideEncryption, IfNoneMatch=None):
        if IfNoneMatch == "*" and (self.region, Bucket, Key) in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed", "Message": "exists"}}, "PutObject")
        return super().put_object(Bucket=Bucket, Key=Key, Body=Body, ContentType=ContentType, ServerSideEncryption=ServerSideEncryption)

    def list_objects_v2(self, Bucket, Prefix, MaxKeys):
        keys = sorted(k for r, b, k in self.objects if r == self.region and b == Bucket and k.startswith(Prefix))
        return {"Contents": [{"Key": k} for k in keys[:MaxKeys]], "IsTruncated": len(keys) > MaxKeys}


class UploadFakeSession(FakeSession):
    def client(self, service, region_name, config):
        assert service == "s3"
        self.regions.append(region_name)
        return UploadFakeS3(region_name, self.objects)


def csv_payload(city="berlin", region="eu-west-2", data=None):
    if data is None:
        data = "date,temp_max_c,temp_min_c,precipitation_mm\n2025-07-01,20,11,1.5\n2025-07-02,21,12,0.0\n2025-07-03,22,13,0.5\n"
    return {
        "city": city, "country": "Germany", "region": region,
        "source": "Municipal station", "filename": f"{city}.csv",
        "file_base64": base64.b64encode(data.encode()).decode(),
    }


@pytest.fixture
def publishing_api(settings, monkeypatch):
    monkeypatch.setenv("ENVIROSYNC_UPLOADS_ENABLED", "true")
    monkeypatch.setenv("ENVIROSYNC_HOSTING_ONLY", "false")
    session = UploadFakeSession()
    federation = S3Federation(settings, session=session)
    datasets = {}
    for name, city in settings.cities.items():
        source = sample_api_payload(first="2025-07-01", n=3, timezone=city.timezone)
        datasets[name] = normalize_weather(city, "2025-07-01", "2025-07-03", source, "https://example.invalid")
    federation.publish(datasets)
    app.dependency_overrides[get_federation] = lambda: federation
    app.dependency_overrides[require_admin] = lambda: {"sub": "example-admin-id", "cognito:groups": ["envirosync-admin"]}
    with TestClient(app) as client:
        yield client, session, federation
    app.dependency_overrides.clear()


def test_csv_upload_catalog_observations_comparison_and_original_data_preserved(publishing_api):
    client, session, federation = publishing_api
    original = dict(session.objects)
    result = client.post("/api/admin/datasets", json=csv_payload())
    assert result.status_code == 201, result.text
    assert result.json()["dataset"]["city"] == "berlin"
    assert len(result.json()["dataset"]["sha256"]) == 64
    assert all(session.objects[k] == v for k, v in original.items())
    catalog = client.get("/api/datasets")
    assert catalog.status_code == 200, catalog.text
    assert [d["city"] for d in catalog.json()["datasets"]] == ["chennai", "london", "berlin"]
    berlin = catalog.json()["datasets"][-1]
    assert "bucket" not in berlin and berlin["aws_region"] == "eu-west-2"
    response = client.get("/api/observations", params={"city": "berlin", "start": "2025-07-01", "end": "2025-07-03"})
    assert response.status_code == 200, response.text
    assert response.json()["sha256_verified"] is True
    assert response.json()["row_count"] == 3
    assert response.json()["rows"][1]["temp_max_c"] == 21.0
    compare = client.get("/api/compare", params={"city1": "berlin", "city2": "chennai", "start": "2025-07-01", "end": "2025-07-03"})
    assert compare.status_code == 200, compare.text
    assert len(compare.json()["points"]) == 3
    assert compare.json()["sources"]["berlin"]["sha256_verified"] is True
    assert set(session.regions) == {"ap-south-1", "eu-west-2"}


def test_json_upload_into_mumbai_region(publishing_api):
    client, session, federation = publishing_api
    rows = [{"date": "2025-07-01", "temp_max_c": 32, "temp_min_c": 23, "precipitation_mm": 0}]
    payload = csv_payload("pune", "ap-south-1")
    payload["filename"] = "pune.json"
    payload["file_base64"] = base64.b64encode(json.dumps(rows).encode()).decode()
    response = client.post("/api/admin/datasets", json=payload)
    assert response.status_code == 201, response.text
    assert ("ap-south-1", federation.settings.catalog_bucket, f"{DATA_PREFIX}pune.json") in session.objects
    assert client.get("/api/observations", params={"city": "pune", "start": "2025-07-01", "end": "2025-07-01"}).json()["sha256_verified"] is True


def test_duplicate_and_legacy_city_overwrite_blocked(publishing_api):
    client, session, federation = publishing_api
    assert client.post("/api/admin/datasets", json=csv_payload()).status_code == 201
    response = client.post("/api/admin/datasets", json=csv_payload())
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DATASET_EXISTS"
    response = client.post("/api/admin/datasets", json=csv_payload("chennai"))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CITY"


@pytest.mark.parametrize("rows, expected", [
    ("date,temp_max_c,temp_min_c,precipitation_mm\n2025-07-01,3,5,0\n", "INVALID_VALUES"),
    ("date,temp_max_c,temp_min_c,precipitation_mm\n2025-07-01,8,5,-1\n", "INVALID_VALUES"),
    ("date,temp_max_c,temp_min_c,precipitation_mm\n2025-07-01,nan,5,0\n", "INVALID_VALUES"),
    ("date,temp_max_c,temp_min_c,precipitation_mm\n2025-07-01,8,5,0\n2025-07-03,8,5,0\n", "MISSING_DATES"),
    ("date,temp_max_c,temp_min_c,precipitation_mm\n2025-07-01,8,5,0\n2025-07-01,8,5,0\n", "MISSING_DATES"),
    ("date,max_temp,min_temp,precipitation_mm\n2025-07-01,8,5,0\n", "INVALID_COLUMNS"),
])
def test_invalid_daily_csv_rejected_before_writes(publishing_api, rows, expected):
    client, session, _ = publishing_api
    before = len(session.objects)
    response = client.post("/api/admin/datasets", json=csv_payload(data=rows))
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == expected
    assert len(session.objects) == before


def test_invalid_region_and_oversize_rejected(publishing_api):
    client, session, _ = publishing_api
    assert client.post("/api/admin/datasets", json=csv_payload(region="us-east-1")).status_code == 400
    payload = csv_payload()
    payload["file_base64"] = base64.b64encode(b"A" * 200001).decode()
    response = client.post("/api/admin/datasets", json=payload)
    assert response.status_code == 413, response.text


def test_tampered_uploaded_data_and_registry_fail_closed(publishing_api):
    client, session, federation = publishing_api
    assert client.post("/api/admin/datasets", json=csv_payload()).status_code == 201
    key = ("eu-west-2", federation.settings.city("london").bucket, f"{DATA_PREFIX}berlin.json")
    session.objects[key] = session.objects[key].replace(b"20.0", b"99.0")
    response = client.get("/api/observations", params={"city": "berlin", "start": "2025-07-01", "end": "2025-07-03"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "INVALID_REMOTE_DATA"
    manifest_key = ("ap-south-1", federation.settings.catalog_bucket, f"{REGISTRY_PREFIX}berlin.json")
    meta = json.loads(session.objects[manifest_key])
    meta["bucket"] = "unauthorized-bucket"
    session.objects[manifest_key] = json.dumps(meta).encode()
    assert client.get("/api/datasets").status_code == 502


def test_missing_admin_bearer_denies_before_s3(publishing_api, monkeypatch):
    client, session, federation = publishing_api
    app.dependency_overrides.pop(require_admin)
    monkeypatch.setenv("ENVIROSYNC_COGNITO_USER_POOL_ID", "ap-south-1_TEST123")
    monkeypatch.setenv("ENVIROSYNC_COGNITO_CLIENT_ID", "examplebrowserclient")
    before = len(session.objects)
    response = client.post("/api/admin/datasets", json=csv_payload())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"
    assert len(session.objects) == before


def test_uploads_off_by_default_protects_write_endpoint(publishing_api, monkeypatch):
    client, session, _ = publishing_api
    app.dependency_overrides.pop(require_admin)
    monkeypatch.setenv("ENVIROSYNC_UPLOADS_ENABLED", "false")
    before = len(session.objects)
    response = client.post("/api/admin/datasets", json=csv_payload())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UPLOADS_DISABLED"
    assert len(session.objects) == before


def test_wrong_group_cannot_upload_even_with_signed_jwt(publishing_api, monkeypatch):
    from milestones.milestone_2_api import admin_auth
    client, session, _ = publishing_api
    app.dependency_overrides.pop(require_admin)
    monkeypatch.setenv("ENVIROSYNC_COGNITO_USER_POOL_ID", "ap-south-1_TEST123")
    monkeypatch.setenv("ENVIROSYNC_COGNITO_CLIENT_ID", "examplebrowserclient")
    monkeypatch.setattr(admin_auth, "jwks_client", lambda _: SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key="fake")))
    monkeypatch.setattr(admin_auth.jwt, "decode", lambda *args, **kwargs: {
        "token_use": "access", "client_id": "examplebrowserclient", "cognito:groups": ["readers"]
    })
    before = len(session.objects)
    response = client.post("/api/admin/datasets", headers={"Authorization": "Bearer signed-token"}, json=csv_payload())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_REQUIRED"
    assert len(session.objects) == before


def test_rs256_signature_issuer_client_and_group_are_enforced(publishing_api, monkeypatch):
    """Use real PyJWT RS256 verification against a mocked public JWKS key."""
    import jwt
    from datetime import datetime, timezone
    from cryptography.hazmat.primitives.asymmetric import rsa
    from milestones.milestone_2_api import admin_auth

    client, session, _ = publishing_api
    app.dependency_overrides.pop(require_admin)
    monkeypatch.setenv("ENVIROSYNC_COGNITO_USER_POOL_ID", "ap-south-1_TEST123")
    monkeypatch.setenv("ENVIROSYNC_COGNITO_CLIENT_ID", "browser-client")
    correct = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(admin_auth, "jwks_client", lambda _: SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=correct.public_key())))
    now = int(datetime.now(timezone.utc).timestamp())
    standard = {
        "iss": "https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_TEST123",
        "sub": "admin-id", "client_id": "browser-client", "token_use": "access",
        "cognito:groups": ["envirosync-admin"], "iat": now, "exp": now + 600,
    }

    def post(claims, key=correct):
        token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})
        return client.post("/api/admin/datasets", json=csv_payload("hamburg"), headers={"Authorization": f"Bearer {token}"})

    for updates in (
        {"client_id": "different-browser-client"},
        {"iss": "https://untrusted.example.com/"},
        {"token_use": "id"},
        {"cognito:groups": ["not-admin"]},
        {"exp": now - 600},
    ):
        response = post({**standard, **updates})
        assert response.status_code in (401, 403), response.text
    assert post(standard, key=other).status_code == 401
    assert post(standard).status_code == 201
