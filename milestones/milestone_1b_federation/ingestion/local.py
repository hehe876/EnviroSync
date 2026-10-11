"""Local staging of real historical datasets; no AWS calls."""
import json
from pathlib import Path
from .weather import fetch_weather, parse_interval, validate_dataset
from milestones.milestone_1b_federation.common import to_json_bytes

def fetch_both(settings, start, end, output_dir):
    parse_interval(start, end)
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    datasets = {}
    for name, city in settings.cities.items():
        print(f"Fetching real {name} ERA5 historical data ({start} to {end})...", flush=True)
        data = fetch_weather(city, start, end)
        datasets[name] = data
        path = folder / f"{name}-daily-weather.json"
        path.write_bytes(to_json_bytes(data))
        print(f"  Saved {data['observation_count']} observations to {path}")
    return datasets


def load_prepared(settings, start, end, output_dir):
    parse_interval(start, end)
    datasets = {}
    for name, city in settings.cities.items():
        path = Path(output_dir) / f"{name}-daily-weather.json"
        if not path.is_file():
            raise ValueError(f"Missing {path}. First run the fetch command for the same date range.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Malformed local preview file: {path}") from exc
        validate_dataset(data, city)
        if (data["start_date"], data["end_date"]) != (start, end):
            raise ValueError(f"Preview dates in {path} differ from --start and --end")
        datasets[name] = data
    return datasets


