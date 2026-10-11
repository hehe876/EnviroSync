"""Prove API delegates to the single Milestone 1B federation block."""
from fastapi.testclient import TestClient
from milestones.milestone_2_api import app
from milestones.milestone_2_api.routes import router
from milestones.milestone_1b_federation.federation import S3Federation
from milestones.milestone_2_api.dependencies import get_federation

def test_api_uses_real_federation_type():
    assert S3Federation.__module__.startswith("milestones.milestone_1b_federation.")
    assert get_federation.__wrapped__.__globals__["S3Federation"] is S3Federation

def test_api_health_does_not_claim_aws_verified():
    with TestClient(app) as client:
        data = client.get("/api/health").json()
    assert data["aws_checked"] is False
    assert data["status"] == "ok"

def test_route_dependencies_reference_milestone_1b():
    route_paths = {r.path for r in router.routes}
    assert {"/api/datasets", "/api/observations", "/api/compare"}.issubset(route_paths)
    from milestones.milestone_2_api import routes
    assert routes.S3Federation is S3Federation
