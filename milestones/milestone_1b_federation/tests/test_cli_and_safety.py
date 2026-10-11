import pytest

from milestones.milestone_1b_federation.ingestion.local import load_prepared
from milestones.milestone_1b_federation.federation import S3Federation
from milestones.milestone_1b_federation.storage import to_json_bytes
from milestones.milestone_1b_federation.ingestion import normalize_weather
from conftest import sample_api_payload


def make_previews(settings, directory):
    for name, city in settings.cities.items():
        payload = sample_api_payload(timezone=city.timezone)
        data = normalize_weather(city, "2025-07-01", "2025-07-03", payload, "https://example.invalid/test")
        (directory / f"{name}-daily-weather.json").write_bytes(to_json_bytes(data))


def test_load_local_preview_before_aws(settings, tmp_path):
    make_previews(settings, tmp_path)
    values = load_prepared(settings, "2025-07-01", "2025-07-03", tmp_path)
    assert values["london"]["observation_count"] == 3
    assert values["chennai"]["source"]["provider"] == "Open-Meteo"


def test_publish_refuses_missing_preview(settings, tmp_path):
    with pytest.raises(ValueError, match="Missing"):
        load_prepared(settings, "2025-07-01", "2025-07-03", tmp_path)


def test_publish_refuses_wrong_preview_dates(settings, tmp_path):
    make_previews(settings, tmp_path)
    with pytest.raises(ValueError, match="Preview dates"):
        load_prepared(settings, "2025-07-02", "2025-07-03", tmp_path)


def test_retrieval_rejects_invalid_date(settings, fake_session):
    store = S3Federation(settings, session=fake_session)
    data = {}
    for name, city in settings.cities.items():
        data[name] = normalize_weather(city, "2025-07-01", "2025-07-03", sample_api_payload(timezone=city.timezone), "test")
    store.publish(data)
    with pytest.raises(ValueError, match="valid YYYY-MM-DD"):
        store.retrieve("london", start="2025-07-32")
