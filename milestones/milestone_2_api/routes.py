"""Read-only HTTP routes; all S3 work goes through S3Federation."""
import os
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, Query
from milestones.milestone_1b_federation.federation import S3Federation
from .dependencies import get_federation, hosting_only
from .errors import ApiProblem
from .services import METRICS, checked_city, checked_dates, checked_catalog, ensure_coverage, normalize_row, align_series

router = APIRouter()

@router.get("/api/health")
def health():
    """Local-process health only; no AWS calls or S3 assertions."""
    return {"status": "ok", "service": "envirosync-api", "aws_checked": False}


@router.get("/api/datasets")
def datasets(federation: S3Federation = Depends(get_federation)):
    if hosting_only():
        # Deliberately empty: zero S3 calls, no fake data, no bucket permissions.
        return {"schema_version": "1.0", "datasets": []}
    try:
        catalog = checked_catalog(federation)
    except ClientError as exc:
        # Hosting bootstrap: distinguish an absent catalog from IAM/S3 outages.
        # Fail closed for every other AWS error. No sample data is fabricated.
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
                "display_name": entry["city"].title(),
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
    name = checked_city(city, federation)
    checked_dates(start, end)
    catalog = checked_catalog(federation)
    ensure_coverage(catalog, name, start, end)
    data = federation.retrieve(name, start, end)
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
    first_name = checked_city(city1, federation)
    second_name = checked_city(city2, federation)
    if first_name == second_name:
        raise ApiProblem(400, "DUPLICATE_CITIES", "Select two distinct cities for comparison.")
    if metric not in METRICS:
        raise ApiProblem(400, "UNKNOWN_METRIC", f"Metric must be one of: {', '.join(METRICS)}.")
    checked_dates(start, end)
    catalog = checked_catalog(federation)
    ensure_coverage(catalog, first_name, start, end)
    ensure_coverage(catalog, second_name, start, end)
    first = federation.retrieve(first_name, start, end)
    second = federation.retrieve(second_name, start, end)
    return align_series(first_name, second_name, metric, first, second)
