"""Read-only federation API and Cognito-admin-only dataset publishing API."""
import os
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, Query, Response

from milestones.milestone_1b_federation.federation import S3Federation
from .admin_auth import require_admin, uploads_enabled
from .dependencies import get_federation, hosting_only
from .errors import ApiProblem
from .services import METRICS, checked_dates, checked_catalog, ensure_coverage, normalize_row, align_series
from .upload_service import UploadRequest, UploadService

router = APIRouter()


def full_catalog(federation):
    catalog = checked_catalog(federation)
    if not uploads_enabled():
        return catalog
    uploads = UploadService(federation).list_entries()
    return {**catalog, "datasets": [*catalog["datasets"], *uploads]}


def require_city(city, catalog):
    normalized = city.strip().lower()
    if not any(entry["city"] == normalized for entry in catalog["datasets"]):
        raise ApiProblem(404, "DATASET_NOT_FOUND", "No dataset is registered for this city.")
    return normalized


def fetch_city(federation, catalog, city, start, end):
    entry = ensure_coverage(catalog, city, start, end)
    if city in federation.settings.cities:
        return federation.retrieve(city, start, end)
    return UploadService(federation).retrieve(entry, start, end)


@router.get("/api/health")
def health():
    return {"status": "ok", "service": "envirosync-api", "aws_checked": False}


@router.get("/api/datasets")
def datasets(federation: S3Federation = Depends(get_federation)):
    if hosting_only():
        return {"schema_version": "1.0", "datasets": []}
    try:
        catalog = full_catalog(federation)
    except ClientError as exc:
        if (os.getenv("ENVIROSYNC_ALLOW_EMPTY_CATALOG", "false").lower() == "true"
                and exc.response.get("Error", {}).get("Code") == "NoSuchKey"):
            catalog = {"schema_version": "1.0", "datasets": []}
        else:
            raise
    return {
        "schema_version": catalog["schema_version"],
        "datasets": [
            {
                "dataset_id": entry["dataset_id"],
                "city": entry["city"],
                "display_name": entry["city"].replace("-", " ").title(),
                "country": entry["country"],
                "aws_region": entry["region"],
                "source": entry["source"],
                "variables": list(METRICS),
                "start_date": entry["start_date"],
                "end_date": entry["end_date"],
                "observation_count": entry["observation_count"],
                "timezone": entry["timezone"],
            }
            for entry in catalog["datasets"]
        ],
    }


@router.get("/api/observations")
def observations(
    city: str = Query(min_length=1, max_length=40),
    start: str = Query(min_length=10, max_length=10),
    end: str = Query(min_length=10, max_length=10),
    federation: S3Federation = Depends(get_federation),
):
    if hosting_only():
        raise ApiProblem(503, "DATA_NOT_CONNECTED", "Environmental data integration is disabled in hosting-only mode.")
    checked_dates(start, end)
    catalog = full_catalog(federation)
    name = require_city(city, catalog)
    data = fetch_city(federation, catalog, name, start, end)
    return {
        "city": name,
        "aws_region": data["region"],
        "metric_units": {key: unit for key, (_, unit) in METRICS.items()},
        "source": data["source"]["provider"],
        "provenance": data["source"],
        "dataset_version": "1.0",
        "requested_start": start,
        "requested_end": end,
        "row_count": len(data["observations"]),
        "sha256_verified": data["sha256_verified"],
        "rows": [normalize_row(row) for row in data["observations"]],
    }


@router.get("/api/compare")
def compare(
    city1: str = Query(min_length=1, max_length=40),
    city2: str = Query(min_length=1, max_length=40),
    start: str = Query(min_length=10, max_length=10),
    end: str = Query(min_length=10, max_length=10),
    metric: str = Query(default="temp_max_c"),
    federation: S3Federation = Depends(get_federation),
):
    if hosting_only():
        raise ApiProblem(503, "DATA_NOT_CONNECTED", "Environmental data integration is disabled in hosting-only mode.")
    if metric not in METRICS:
        raise ApiProblem(400, "UNKNOWN_METRIC", f"Metric must be one of: {', '.join(METRICS)}.")
    checked_dates(start, end)
    catalog = full_catalog(federation)
    first_name = require_city(city1, catalog)
    second_name = require_city(city2, catalog)
    if first_name == second_name:
        raise ApiProblem(400, "DUPLICATE_CITIES", "Select two distinct cities for comparison.")
    first = fetch_city(federation, catalog, first_name, start, end)
    second = fetch_city(federation, catalog, second_name, start, end)
    return align_series(first_name, second_name, metric, first, second)


@router.get("/api/admin/session")
def admin_session(claims: dict = Depends(require_admin)):
    return {"admin": True, "username": claims.get("username", "administrator")}


@router.post("/api/admin/datasets", status_code=201)
def admin_publish_dataset(
    payload: UploadRequest,
    response: Response,
    claims: dict = Depends(require_admin),
    federation: S3Federation = Depends(get_federation),
):
    if hosting_only():
        raise ApiProblem(503, "DATA_NOT_CONNECTED", "S3 federation is disabled.")
    entry = UploadService(federation).publish(payload, claims.get("sub", "administrator"))
    response.headers["Cache-Control"] = "no-store"
    return {
        "created": True,
        "dataset": {
            "dataset_id": entry["dataset_id"], "city": entry["city"],
            "country": entry["country"], "aws_region": entry["region"],
            "start_date": entry["start_date"], "end_date": entry["end_date"],
            "observation_count": entry["observation_count"],
            "sha256": entry["sha256"],
        },
    }
