"""Read-only HTTPS smoke test for original M4B federation and M4C admin denial."""
import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def get(url):
    with urlopen(Request(url, headers={"User-Agent": "EnviroSync-M4C-Smoke/1.0", "Accept": "application/json,text/html"}), timeout=25) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read(300_000).decode("utf-8")


def smoke(base_url, expect_empty=False, hosting_only=False):
    base = base_url.rstrip("/")
    if not base.startswith("https://"):
        raise ValueError("Use the HTTPS CloudFront WebsiteUrl")
    _, kind, html = get(base + "/")
    if "text/html" not in kind or '<div id="root">' not in html:
        raise AssertionError("React HTML unavailable")
    print("PASS: React HTML served over HTTPS", flush=True)
    _, _, body = get(base + "/api/health")
    health = json.loads(body)
    if health.get("status") != "ok" or health.get("aws_checked") is not False:
        raise AssertionError("Unexpected health contract")
    print("PASS: API health", flush=True)
    _, _, body = get(base + "/api/datasets")
    catalog = json.loads(body)
    if not isinstance(catalog.get("datasets"), list):
        raise AssertionError("Invalid dataset catalog")
    if expect_empty and catalog["datasets"]:
        raise AssertionError("Expected empty catalog")
    print(f"PASS: catalog ({len(catalog['datasets'])} datasets)", flush=True)
    if not hosting_only and not expect_empty:
        cities = {x.get("city") for x in catalog["datasets"]}
        if not {"chennai", "london"}.issubset(cities):
            raise AssertionError(f"Original Chennai/London datasets missing: {cities}")
        print("PASS: Original regional datasets preserved", flush=True)
        for city in ("chennai", "london"):
            query = urlencode({"city": city, "start": "2025-07-01", "end": "2025-07-07"})
            _, _, body = get(base + "/api/observations?" + query)
            data = json.loads(body)
            if data.get("city") != city or data.get("row_count") != 7 or data.get("sha256_verified") is not True:
                raise AssertionError(f"Observations/integrity failed for {city}")
            print(f"PASS: {city.title()} SHA-256 and observations", flush=True)
        query = urlencode({"city1": "chennai", "city2": "london", "start": "2025-07-01", "end": "2025-07-07", "metric": "temp_max_c"})
        _, _, body = get(base + "/api/compare?" + query)
        if len(json.loads(body).get("points", [])) != 7:
            raise AssertionError("Cross-region comparison failed")
        print("PASS: Cross-region comparison", flush=True)
        try:
            get(base + "/api/admin/session")
        except HTTPError as exc:
            if exc.code not in (401, 503):
                raise AssertionError(f"Unauthenticated admin session returned HTTP {exc.code}") from exc
        else:
            raise AssertionError("Unauthenticated administrator session incorrectly allowed")
        print("PASS: Administrator routes deny anonymous sessions", flush=True)
    if hosting_only:
        query = urlencode({"city": "chennai", "start": "2025-01-01", "end": "2025-01-02"})
        try:
            get(base + "/api/observations?" + query)
        except HTTPError as exc:
            if exc.code != 503 or json.loads(exc.read().decode()).get("error", {}).get("code") != "DATA_NOT_CONNECTED":
                raise AssertionError("Hosting-only data endpoint returned incorrect error") from exc
        else:
            raise AssertionError("Hosting-only data unexpectedly connected")
    print("SUCCESS: EnviroSync M4C smoke test passed", flush=True)
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--expect-empty", action="store_true")
    parser.add_argument("--hosting-only", action="store_true")
    args = parser.parse_args()
    try:
        smoke(args.url, expect_empty=args.expect_empty, hosting_only=args.hosting_only)
        return 0
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, AssertionError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
