"""API-specific validation, presentation and two-city series alignment."""
from datetime import date
from .errors import ApiProblem

MAX_DAYS = 31
METRICS = {
    "temp_max_c": ("max_temp_c", "°C"),
    "temp_min_c": ("min_temp_c", "°C"),
    "precipitation_mm": ("precipitation_mm", "mm"),
}

def checked_city(city, federation):
    normalized = city.strip().lower()
    if normalized not in federation.settings.cities:
        raise ApiProblem(404, "DATASET_NOT_FOUND", "No dataset is registered for this city.")
    return normalized


def checked_dates(start, end):
    try:
        begin, finish = date.fromisoformat(start), date.fromisoformat(end)
        if begin.isoformat() != start or finish.isoformat() != end:
            raise ValueError("not canonical ISO format")
    except (TypeError, ValueError) as exc:
        raise ApiProblem(400, "INVALID_DATE", "Use valid calendar dates in YYYY-MM-DD format.") from exc
    if finish < begin:
        raise ApiProblem(400, "INVALID_DATE_RANGE", "End date must not precede start date.")
    if (finish - begin).days + 1 > MAX_DAYS:
        raise ApiProblem(400, "DATE_RANGE_TOO_LARGE", f"Select at most {MAX_DAYS} inclusive calendar days.")
    return begin, finish


def checked_catalog(federation):
    return federation.discover()


def entry_for_city(catalog, city):
    return next(item for item in catalog["datasets"] if item["city"] == city)


def ensure_coverage(catalog, city, start, end):
    entry = entry_for_city(catalog, city)
    if start < entry["start_date"] or end > entry["end_date"]:
        raise ApiProblem(
            400, "OUTSIDE_DATASET_COVERAGE",
            f"{city.title()} supports dates from {entry['start_date']} to {entry['end_date']}.",
        )
    return entry


def normalize_row(row):
    return {
        "date": row["date"],
        "temp_max_c": row["max_temp_c"],
        "temp_min_c": row["min_temp_c"],
        "precipitation_mm": row["precipitation_mm"],
    }


def align_series(city1, city2, metric, first, second):
    original_key, unit = METRICS[metric]
    rows_first = {row["date"]: row[original_key] for row in first["observations"]}
    rows_second = {row["date"]: row[original_key] for row in second["observations"]}
    dates = sorted(set(rows_first) | set(rows_second))
    return {
        "city1": city1,
        "city2": city2,
        "metric": metric,
        "unit": unit,
        "points": [
            {"date": day, city1: rows_first.get(day), city2: rows_second.get(day)}
            for day in dates
        ],
        "missing_policy": "null_means_unavailable",
        "sources": {
            city1: {"aws_region": first["region"], "source": first["source"]["provider"], "sha256_verified": first["sha256_verified"]},
            city2: {"aws_region": second["region"], "source": second["source"]["provider"], "sha256_verified": second["sha256_verified"]},
        },
    }


