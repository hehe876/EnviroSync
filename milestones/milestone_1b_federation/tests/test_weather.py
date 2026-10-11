import pytest

from milestones.milestone_1b_federation.ingestion import normalize_weather, parse_interval, validate_dataset
from conftest import sample_api_payload


def test_normalize_actual_api_shape(settings):
    city = settings.city("chennai")
    result = normalize_weather(city, "2025-07-01", "2025-07-03", sample_api_payload(), "https://example.invalid/test")
    assert result["observation_count"] == 3
    assert result["observations"][2]["max_temp_c"] == 32.0
    assert result["source"]["dataset"] == "ERA5 historical reanalysis"
    assert validate_dataset(result, city)


def test_reject_missing_day(settings):
    payload = sample_api_payload()
    payload["daily"]["time"][1] = "2025-07-03"
    with pytest.raises(ValueError, match="chronological"):
        normalize_weather(settings.city("chennai"), "2025-07-01", "2025-07-03", payload, "test")


def test_reject_missing_temperature(settings):
    payload = sample_api_payload()
    payload["daily"]["temperature_2m_max"][1] = None
    with pytest.raises(ValueError, match="Missing or invalid"):
        normalize_weather(settings.city("chennai"), "2025-07-01", "2025-07-03", payload, "test")


def test_reject_wrong_timezone(settings):
    with pytest.raises(ValueError, match="timezone"):
        normalize_weather(settings.city("london"), "2025-07-01", "2025-07-03", sample_api_payload(), "test")


def test_reject_invalid_interval():
    with pytest.raises(ValueError, match="chronological"):
        parse_interval("2025-07-10", "2025-07-01")
    with pytest.raises(ValueError, match="at most"):
        parse_interval("2020-01-01", "2025-01-01")


def test_reject_fabricated_values(settings):
    city = settings.city("chennai")
    result = normalize_weather(city, "2025-07-01", "2025-07-03", sample_api_payload(), "test")
    result["observations"][0]["precipitation_mm"] = -1
    with pytest.raises(ValueError, match="inconsistent"):
        validate_dataset(result, city)
