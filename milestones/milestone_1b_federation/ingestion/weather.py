"""Download and validate daily ERA5 historical observations from Open-Meteo."""

from datetime import date, datetime, timedelta, timezone
import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SOURCE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_FIELDS = ("temperature_2m_max", "temperature_2m_min", "precipitation_sum")
MAX_RESPONSE_BYTES = 2_000_000


def parse_interval(start, end):
    if not isinstance(start, str) or not isinstance(end, str):
        raise ValueError("Dates must use YYYY-MM-DD")
    try:
        first = date.fromisoformat(start)
        last = date.fromisoformat(end)
    except ValueError as exc:
        raise ValueError("Dates must use YYYY-MM-DD") from exc
    if last < first or (last - first).days > 800:
        raise ValueError("Select a chronological date range of at most 801 days")
    if last >= date.today():
        raise ValueError("Historical end date must be before today")
    return first, last


def fetch_weather(city, start, end):
    first, last = parse_interval(start, end)
    params = {
        "latitude": city.latitude,
        "longitude": city.longitude,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(DAILY_FIELDS),
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
        "timezone": city.timezone,
        "models": "era5",
    }
    url = f"{SOURCE_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "EnviroSync-educational-prototype/1.0"})
    try:
        with urlopen(request, timeout=40) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        reason = exc.read(400).decode("utf-8", errors="replace")
        raise RuntimeError(f"Open-Meteo returned HTTP {exc.code}: {reason}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not reach Open-Meteo: {exc}") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Open-Meteo response exceeds the 2 MB safety limit")
    try:
        response = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Open-Meteo did not return valid JSON") from exc
    return normalize_weather(city, start, end, response, url)


def normalize_weather(city, start, end, response, url):
    first, last = parse_interval(start, end)
    if not isinstance(response, dict) or response.get("error"):
        raise ValueError(f"Weather API reported an error: {response.get('reason', 'unknown') if isinstance(response, dict) else 'bad format'}")
    daily = response.get("daily")
    if not isinstance(daily, dict):
        raise ValueError("Open-Meteo response is missing the daily values")
    days = daily.get("time")
    expected_count = (last - first).days + 1
    if not isinstance(days, list) or len(days) != expected_count:
        raise ValueError("Weather API did not return the entire requested date range")
    for field in DAILY_FIELDS:
        if not isinstance(daily.get(field), list) or len(daily[field]) != expected_count:
            raise ValueError(f"Weather API is missing or misaligning '{field}'")

    daily_units = response.get("daily_units", {})
    if not isinstance(daily_units, dict):
        raise ValueError("Invalid units in weather API response")
    if daily_units.get("temperature_2m_max") != "°C" or daily_units.get("temperature_2m_min") != "°C" or daily_units.get("precipitation_sum") != "mm":
        raise ValueError("Unexpected units returned by Open-Meteo; expected Celsius and millimeters")
    if response.get("timezone") != city.timezone:
        raise ValueError(f"Unexpected timezone: {response.get('timezone')!r}")

    observations = []
    for index, current in enumerate(days):
        expected_day = first + timedelta(days=index)
        if current != expected_day.isoformat():
            raise ValueError("Dates must be chronological, complete, and nonduplicated")
        readings = [daily[field][index] for field in DAILY_FIELDS]
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in readings):
            raise ValueError(f"Missing or invalid weather reading on {current}; refusing incomplete ingestion")
        maximum, minimum, rain = (float(value) for value in readings)
        if maximum < minimum or rain < 0:
            raise ValueError(f"Invalid temperature range or rainfall on {current}")
        observations.append({
            "date": current,
            "max_temp_c": maximum,
            "min_temp_c": minimum,
            "precipitation_mm": rain,
        })

    return {
        "schema_version": "1.0",
        "dataset_id": f"{city.name}-daily-weather-era5",
        "city": city.name,
        "country": city.country,
        "coordinates": {"latitude": city.latitude, "longitude": city.longitude},
        "data_timezone": city.timezone,
        "start_date": start,
        "end_date": end,
        "observation_count": len(observations),
        "source": {
            "provider": "Open-Meteo",
            "dataset": "ERA5 historical reanalysis",
            "url": url,
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "attribution": "Open-Meteo (open-meteo.com); ERA5 / Copernicus Climate Change Service",
            "note": "Model-derived historical reanalysis, not municipal sensor measurements",
        },
        "observations": observations,
    }


def validate_dataset(data, city):
    if not isinstance(data, dict) or data.get("schema_version") != "1.0":
        raise ValueError("Unrecognized dataset schema version")
    if data.get("city") != city.name or data.get("dataset_id") != f"{city.name}-daily-weather-era5":
        raise ValueError("Dataset identity does not match the requested city")
    if data.get("data_timezone") != city.timezone:
        raise ValueError("Dataset timezone does not match the expected city")
    if not isinstance(data.get("source"), dict) or data["source"].get("provider") != "Open-Meteo":
        raise ValueError("Dataset provenance is missing")
    first, last = parse_interval(data.get("start_date", ""), data.get("end_date", ""))
    observations = data.get("observations")
    if not isinstance(observations, list) or len(observations) != data.get("observation_count"):
        raise ValueError("Dataset observation_count does not match the data")
    if len(observations) != (last - first).days + 1:
        raise ValueError("Dataset contains missing dates")
    for index, item in enumerate(observations):
        if not isinstance(item, dict) or item.get("date") != (first + timedelta(days=index)).isoformat():
            raise ValueError("Dataset dates are incomplete or unordered")
        values = [item.get("max_temp_c"), item.get("min_temp_c"), item.get("precipitation_mm")]
        if any(type(value) not in (float, int) or not math.isfinite(value) for value in values):
            raise ValueError("Dataset contains missing or invalid numerical values")
        if values[0] < values[1] or values[2] < 0:
            raise ValueError("Dataset contains inconsistent values")
    return True
