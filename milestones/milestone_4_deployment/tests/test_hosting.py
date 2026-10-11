"""Hosting contract checks; AWS credentials and network are never used."""
import importlib.util
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from milestones.milestone_2_api import app, get_federation

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "milestones" / "milestone_4_deployment" / "scripts" / "stage_lambda.py"
TEMPLATE = ROOT / "milestones" / "milestone_4_deployment" / "infrastructure" / "template.yaml"


def aws_error(code):
    return ClientError({"Error": {"Code": code, "Message": "fake S3 error"}}, "GetObject")


@pytest.fixture
def empty_catalog_backend():
    class MissingCatalog:
        def discover(self):
            raise aws_error("NoSuchKey")
    app.dependency_overrides[get_federation] = lambda: MissingCatalog()
    yield
    app.dependency_overrides.clear()


def test_no_catalog_is_friendly_when_bootstrap_enabled(empty_catalog_backend, monkeypatch):
    monkeypatch.setenv("ENVIROSYNC_ALLOW_EMPTY_CATALOG", "true")
    with TestClient(app) as client:
        response = client.get("/api/datasets")
        health = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"schema_version": "1.0", "datasets": []}
    assert health.json()["aws_checked"] is False


def test_missing_catalog_still_errors_when_bootstrap_off(empty_catalog_backend, monkeypatch):
    monkeypatch.delenv("ENVIROSYNC_ALLOW_EMPTY_CATALOG", raising=False)
    with TestClient(app) as client:
        result = client.get("/api/datasets")
    assert result.status_code == 502
    assert result.json()["error"]["code"] == "AWS_REQUEST_FAILED"


@pytest.mark.parametrize("code", ["AccessDenied", "NoSuchBucket", "InvalidAccessKeyId", "RequestTimeout"])
def test_bootstrap_never_masks_aws_failures(code, monkeypatch):
    class ProblemCatalog:
        def discover(self):
            raise aws_error(code)
    monkeypatch.setenv("ENVIROSYNC_ALLOW_EMPTY_CATALOG", "true")
    app.dependency_overrides[get_federation] = lambda: ProblemCatalog()
    try:
        with TestClient(app) as client:
            result = client.get("/api/datasets")
        assert result.status_code == 502
        assert result.json()["error"]["code"] == "AWS_REQUEST_FAILED"
    finally:
        app.dependency_overrides.clear()


def test_lambda_staging_uses_canonical_python_modules(tmp_path):
    spec = importlib.util.spec_from_file_location("env_stage", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = module.stage(root=ROOT, output=tmp_path / "lambda")
    assert (output / "milestones/milestone_2_api/lambda_handler.py").exists()
    assert (output / "milestones/milestone_1b_federation/federation/service.py").exists()
    assert not (output / "milestones/milestone_2_api/tests").exists()
    assert not (output / "milestones/milestone_1b_federation/examples").exists()
    assert "mangum" in (output / "requirements.txt").read_text()


def test_hosting_only_never_initializes_s3_or_uses_credentials(monkeypatch):
    from milestones.milestone_2_api import dependencies
    dependencies.get_federation.cache_clear()
    monkeypatch.setenv("ENVIROSYNC_HOSTING_ONLY", "true")

    def cannot_create(*_args, **_kwargs):
        raise AssertionError("Hosting-only backend tried to initialize AWS")

    monkeypatch.setattr(dependencies, "Settings", cannot_create)
    monkeypatch.setattr(dependencies, "S3Federation", cannot_create)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        response = client.get("/api/datasets")
        assert response.status_code == 200
        assert response.json() == {"schema_version": "1.0", "datasets": []}
        denied = client.get("/api/observations", params={"city": "chennai", "start": "2025-01-01", "end": "2025-01-02"})
        assert denied.status_code == 503
        assert denied.json()["error"]["code"] == "DATA_NOT_CONNECTED"
        compared = client.get("/api/compare", params={"city1": "chennai", "city2": "london", "start": "2025-01-01", "end": "2025-01-02"})
        assert compared.status_code == 503
        assert compared.json()["error"]["code"] == "DATA_NOT_CONNECTED"
    dependencies.get_federation.cache_clear()


def test_free_plan_template_has_no_environmental_bucket_permissions():
    source = TEMPLATE.read_text()
    assert 's3:PutObject' not in source
    assert 's3:DeleteObject' not in source
    assert 's3:GetObject' in source  # CloudFront OAC policy serves frontend only
    assert 'envirosync/v1/catalog/datasets.json' not in source
    assert 'envirosync/v1/datasets/' not in source
    assert 'IndiaBucket' not in source
    assert 'LondonBucket' not in source
    assert "ENVIROSYNC_HOSTING_ONLY: 'true'" in source
    assert 'OriginAccessControl' in source
    assert "PathPattern: '/api/*'" in source
    assert 'CachePolicyId: 4135ea2d-6df8-44a3-9df3-4b5a84be39ad' in source
    assert 'PriceClass_100' in source
    assert 'ReservedConcurrentExecutions:' not in source
    assert 'RetentionInDays: 3' in source
    assert 'Lambda@Edge' not in source
    assert 'AWS::EC2::NatGateway' not in source


def test_preflight_free_plan_requires_active_credits_and_correct_identity():
    import importlib.util
    script = ROOT / "milestones/milestone_4_deployment/scripts/preflight_free_plan.py"
    spec = importlib.util.spec_from_file_location('env_free_preflight', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    now = datetime(2026, 10, 11, tzinfo=timezone.utc)
    ok = {
        'accountId': '123456789012',
        'accountPlanType': 'FREE',
        'accountPlanStatus': 'ACTIVE',
        'accountPlanRemainingCredits': {'amount': 24.56, 'unit': 'USD'},
        'accountPlanExpirationDate': (now + timedelta(days=40)).isoformat(),
    }
    result = module.check({'Account': '123456789012'}, ok, now=now)
    assert result['credits_usd'] == 24.56
    cases = [
        ({'accountPlanType': 'PAID'}, 'ACTIVE'),
        ({'accountPlanStatus': 'EXPIRED'}, 'ACTIVE'),
        ({'accountPlanRemainingCredits': {'amount': 0, 'unit': 'USD'}}, 'ACTIVE'),
        ({'accountPlanExpirationDate': (now - timedelta(seconds=1)).isoformat()}, 'ACTIVE'),
    ]
    for changes, _ in cases:
        with pytest.raises(ValueError):
            module.check({'Account': '123456789012'}, {**ok, **changes}, now=now)
    with pytest.raises(ValueError, match='does not match'):
        module.check({'Account': '999999999999'}, ok, now=now)


def test_free_hosting_deployments_are_preflight_gated():
    script = (ROOT / 'milestones/milestone_4_deployment/scripts/deploy-hosting.ps1').read_text()
    workflow = (ROOT / '.github/workflows/deploy-hosting.yml').read_text()
    assert 'preflight_free_plan.py' in script
    assert 'preflight_free_plan.py' in workflow
    assert 'ConfirmAwsCredits' in script
    assert 'PreflightOnly' in script
    assert 'INDIA_BUCKET' not in workflow
    assert 'LONDON_BUCKET' not in workflow
    assert 'workflow_dispatch:' in workflow


def test_github_ci_uses_oidc_not_static_access_keys():
    text = (ROOT / '.github/workflows/deploy-hosting.yml').read_text()
    assert 'id-token: write' in text
    assert 'configure-aws-credentials' in text
    assert 'AWS_ACCESS_KEY_ID' not in text
    assert 'workflow_dispatch:' in text
