
"""Milestone 4B deployment, security and API contract tests.

These tests do not access real AWS resources.
"""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from milestones.milestone_2_api import app, get_federation

ROOT = Path(__file__).resolve().parents[3]
DEPLOYMENT = ROOT / "milestones" / "milestone_4_deployment"
TEMPLATE = DEPLOYMENT / "infrastructure" / "template.yaml"
STAGING_SCRIPT = DEPLOYMENT / "scripts" / "stage_lambda.py"
SMOKE_SCRIPT = DEPLOYMENT / "scripts" / "check_live_hosting.py"
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-hosting.yml"


def aws_error(code):
    return ClientError(
        {"Error": {"Code": code, "Message": "fake S3 error"}},
        "GetObject",
    )


@pytest.fixture
def empty_catalog_backend():
    class MissingCatalog:
        def discover(self):
            raise aws_error("NoSuchKey")

    app.dependency_overrides[get_federation] = lambda: MissingCatalog()
    yield
    app.dependency_overrides.clear()


def test_no_catalog_is_friendly_when_bootstrap_enabled(
    empty_catalog_backend, monkeypatch
):
    monkeypatch.setenv("ENVIROSYNC_HOSTING_ONLY", "false")
    monkeypatch.setenv("ENVIROSYNC_ALLOW_EMPTY_CATALOG", "true")

    with TestClient(app) as client:
        response = client.get("/api/datasets")
        health = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "datasets": [],
    }
    assert health.json()["aws_checked"] is False


def test_missing_catalog_still_errors_when_bootstrap_off(
    empty_catalog_backend, monkeypatch
):
    monkeypatch.setenv("ENVIROSYNC_HOSTING_ONLY", "false")
    monkeypatch.delenv("ENVIROSYNC_ALLOW_EMPTY_CATALOG", raising=False)

    with TestClient(app) as client:
        response = client.get("/api/datasets")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AWS_REQUEST_FAILED"


@pytest.mark.parametrize(
    "code",
    ["AccessDenied", "NoSuchBucket", "InvalidAccessKeyId", "RequestTimeout"],
)
def test_bootstrap_never_masks_aws_failures(code, monkeypatch):
    class ProblemCatalog:
        def discover(self):
            raise aws_error(code)

    monkeypatch.setenv("ENVIROSYNC_HOSTING_ONLY", "false")
    monkeypatch.setenv("ENVIROSYNC_ALLOW_EMPTY_CATALOG", "true")

    app.dependency_overrides[get_federation] = lambda: ProblemCatalog()

    try:
        with TestClient(app) as client:
            response = client.get("/api/datasets")

        assert response.status_code == 502
        assert response.json()["error"]["code"] == "AWS_REQUEST_FAILED"
    finally:
        app.dependency_overrides.clear()


def test_lambda_staging_uses_canonical_python_modules(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "env_stage", STAGING_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    output = module.stage(
        root=ROOT,
        output=tmp_path / "lambda",
    )

    assert (
        output / "milestones/milestone_2_api/lambda_handler.py"
    ).exists()

    assert (
        output / "milestones/milestone_1b_federation/federation/service.py"
    ).exists()

    assert not (
        output / "milestones/milestone_2_api/tests"
    ).exists()

    assert not (
        output / "milestones/milestone_1b_federation/examples"
    ).exists()

    assert "mangum" in (
        output / "requirements.txt"
    ).read_text()


def test_hosting_only_never_initializes_s3_or_uses_credentials(
    monkeypatch
):
    from milestones.milestone_2_api import dependencies

    dependencies.get_federation.cache_clear()
    monkeypatch.setenv("ENVIROSYNC_HOSTING_ONLY", "true")

    def cannot_create(*args, **kwargs):
        raise AssertionError(
            "Hosting-only backend attempted to initialize AWS"
        )

    monkeypatch.setattr(
        dependencies, "Settings", cannot_create
    )
    monkeypatch.setattr(
        dependencies, "S3Federation", cannot_create
    )

    try:
        with TestClient(app) as client:
            health = client.get("/api/health")
            datasets = client.get("/api/datasets")

            observations = client.get(
                "/api/observations",
                params={
                    "city": "chennai",
                    "start": "2025-01-01",
                    "end": "2025-01-02",
                },
            )

            comparison = client.get(
                "/api/compare",
                params={
                    "city1": "chennai",
                    "city2": "london",
                    "start": "2025-01-01",
                    "end": "2025-01-02",
                },
            )

        assert health.status_code == 200
        assert datasets.status_code == 200
        assert datasets.json()["datasets"] == []

        assert observations.status_code == 503
        assert (
            observations.json()["error"]["code"]
            == "DATA_NOT_CONNECTED"
        )

        assert comparison.status_code == 503
        assert (
            comparison.json()["error"]["code"]
            == "DATA_NOT_CONNECTED"
        )
    finally:
        dependencies.get_federation.cache_clear()


def test_m4b_environment_configuration():
    source = TEMPLATE.read_text(encoding="utf-8")

    expected = [
        "ENVIROSYNC_HOSTING_ONLY: 'false'",
        "ENVIROSYNC_ALLOW_EMPTY_CATALOG: 'false'",
        "INDIA_BUCKET: 'envirosync-chennai-2b13ce3af7'",
        "INDIA_REGION: 'ap-south-1'",
        "LONDON_BUCKET: 'envirosync-london-2b13ce3af7'",
        "LONDON_REGION: 'eu-west-2'",
    ]

    for setting in expected:
        assert setting in source, f"Missing configuration: {setting}"


def test_m4b_lambda_has_exact_read_only_s3_permissions():
    source = TEMPLATE.read_text(encoding="utf-8")

    expected_objects = [
        "arn:aws:s3:::envirosync-chennai-2b13ce3af7/"
        "envirosync/v1/catalog/datasets.json",

        "arn:aws:s3:::envirosync-chennai-2b13ce3af7/"
        "envirosync/v1/datasets/chennai-daily-weather.json",

        "arn:aws:s3:::envirosync-london-2b13ce3af7/"
        "envirosync/v1/datasets/london-daily-weather.json",
    ]

    for object_arn in expected_objects:
        assert object_arn in source

    assert "s3:GetObject" in source
    assert "s3:PutObject" not in source
    assert "s3:DeleteObject" not in source
    assert "s3:ListBucket" not in source


def test_m4b_template_preserves_free_plan_infrastructure():
    source = TEMPLATE.read_text(encoding="utf-8")

    required = [
        "OriginAccessControl",
        "PathPattern: '/api/*'",
        "CachePolicyId: 4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
        "PriceClass_100",
        "RetentionInDays: 3",
    ]

    for item in required:
        assert item in source

    forbidden = [
        "ReservedConcurrentExecutions:",
        "Lambda@Edge",
        "AWS::EC2::NatGateway",
    ]

    for item in forbidden:
        assert item not in source


def test_m4b_lambda_policy_is_scoped_to_three_objects():
    source = TEMPLATE.read_text(encoding="utf-8")

    class CloudFormationLoader(yaml.SafeLoader):
        pass

    def cloudformation_tag(loader, tag_suffix, node):
        if isinstance(node, yaml.ScalarNode):
            return loader.construct_scalar(node)
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node)
        return loader.construct_mapping(node)

    CloudFormationLoader.add_multi_constructor(
        "!", cloudformation_tag
    )

    template = yaml.load(
        source,
        Loader=CloudFormationLoader,
    )

    backend = template["Resources"]["Backend"]["Properties"]

    assert backend["Environment"]["Variables"][
        "ENVIROSYNC_HOSTING_ONLY"
    ] == "false"

    statements = []

    for policy in backend["Policies"]:
        statements.extend(policy["Statement"])

    allowed_objects = {
        "arn:aws:s3:::envirosync-chennai-2b13ce3af7/"
        "envirosync/v1/catalog/datasets.json",

        "arn:aws:s3:::envirosync-chennai-2b13ce3af7/"
        "envirosync/v1/datasets/chennai-daily-weather.json",

        "arn:aws:s3:::envirosync-london-2b13ce3af7/"
        "envirosync/v1/datasets/london-daily-weather.json",
    }

    actual_objects = set()

    for statement in statements:
        assert statement["Effect"] == "Allow"
        assert statement["Action"] == ["s3:GetObject"]

        resources = statement["Resource"]

        if isinstance(resources, str):
            resources = [resources]

        actual_objects.update(resources)

    assert actual_objects == allowed_objects


def test_preflight_free_plan_requires_active_credits_and_correct_identity():
    script = DEPLOYMENT / "scripts" / "preflight_free_plan.py"

    spec = importlib.util.spec_from_file_location(
        "env_free_preflight", script
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    now = datetime(2026, 10, 11, tzinfo=timezone.utc)

    ok = {
        "accountId": "123456789012",
        "accountPlanType": "FREE",
        "accountPlanStatus": "ACTIVE",
        "accountPlanRemainingCredits": {
            "amount": 24.56,
            "unit": "USD",
        },
        "accountPlanExpirationDate": (
            now + timedelta(days=40)
        ).isoformat(),
    }

    result = module.check(
        {"Account": "123456789012"},
        ok,
        now=now,
    )

    assert result["credits_usd"] == 24.56

    cases = [
        {"accountPlanType": "PAID"},
        {"accountPlanStatus": "EXPIRED"},
        {
            "accountPlanRemainingCredits": {
                "amount": 0,
                "unit": "USD",
            }
        },
        {
            "accountPlanExpirationDate": (
                now - timedelta(seconds=1)
            ).isoformat()
        },
    ]

    for changes in cases:
        with pytest.raises(ValueError):
            module.check(
                {"Account": "123456789012"},
                {**ok, **changes},
                now=now,
            )

    with pytest.raises(ValueError, match="does not match"):
        module.check(
            {"Account": "999999999999"},
            ok,
            now=now,
        )


def test_free_hosting_deployments_are_preflight_gated():
    script = (
        DEPLOYMENT / "scripts" / "deploy-hosting.ps1"
    ).read_text(encoding="utf-8")

    workflow = WORKFLOW.read_text(encoding="utf-8-sig")

    assert "preflight_free_plan.py" in script
    assert "preflight_free_plan.py" in workflow
    assert "ConfirmAwsCredits" in script
    assert "PreflightOnly" in script

    assert "workflow_dispatch:" in workflow
    assert "INDIA_BUCKET" not in workflow
    assert "LONDON_BUCKET" not in workflow


def test_github_ci_uses_oidc_not_static_access_keys():
    workflow = WORKFLOW.read_text(encoding="utf-8-sig")

    assert "id-token: write" in workflow
    assert "configure-aws-credentials" in workflow
    assert "AWS_ACCESS_KEY_ID" not in workflow
    assert "workflow_dispatch:" in workflow


def test_m4b_workflow_verifies_real_data():
    workflow = WORKFLOW.read_text(encoding="utf-8-sig")

    assert "check_live_hosting.py" in workflow
    assert "--expect-empty" not in workflow
    assert "--hosting-only" not in workflow


def test_m4b_smoke_test_checks_regional_datasets():
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")

    assert "chennai" in source
    assert "london" in source
    assert "/api/observations" in source
    assert "/api/compare" in source
    assert "sha256_verified" in source
