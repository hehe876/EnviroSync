"""EnviroSync M4B HTTPS deployment verification.

Checks:
- React frontend is served over HTTPS
- FastAPI health endpoint is available
- Chennai and London datasets are discovered
- Both cities return historical observations
- SHA-256 integrity verification succeeds
- Cross-region comparison returns aligned data

The script performs read-only HTTP requests.
"""
import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode


def get(url):
    request = Request(url, headers={"User-Agent": "EnviroSync-M4A-SmokeTest/1.0", "Accept": "application/json,text/html"})
    with urlopen(request, timeout=25) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read(300_000).decode("utf-8")


def smoke(base_url, expect_empty=False, hosting_only=False):
    base = base_url.rstrip("/")
    if not base.startswith("https://"):
        raise ValueError("Use the HTTPS CloudFront WebsiteUrl from CloudFormation")
    _, content_type, html = get(base + "/")
    if "text/html" not in content_type or "<div id=\"root\">" not in html:
        raise AssertionError("React index.html not served correctly")
    print("PASS: React HTML served over HTTPS")
    _, _, health_body = get(base + "/api/health")
    health = json.loads(health_body)
    if health.get("status") != "ok" or health.get("aws_checked") is not False:
        raise AssertionError("Unexpected /api/health contract")
    print("PASS: API health reached through the same public hostname")
    _, _, catalog_body = get(base + "/api/datasets")
    catalog = json.loads(catalog_body)
    if not isinstance(catalog.get("datasets"), list):
        raise AssertionError("Unexpected /api/datasets format")
    if expect_empty and catalog["datasets"]:
        raise AssertionError("Expected an empty catalog; actual data is present")
    print(f"PASS: catalog request succeeded ({len(catalog['datasets'])} datasets)")
    if not hosting_only and not expect_empty:
        cities = {item.get("city") for item in catalog["datasets"]}

        if cities != {"chennai", "london"}:
            raise AssertionError(
                f"Expected Chennai and London datasets, got {cities}"
            )

        print("PASS: Chennai and London datasets discovered")

        for city in ("chennai", "london"):
            query = urlencode({
                "city": city,
                "start": "2025-07-01",
                "end": "2025-07-07",
            })

            _, _, response_body = get(
                base + "/api/observations?" + query
            )

            observations = json.loads(response_body)

            if observations.get("city") != city:
                raise AssertionError(
                    f"Incorrect city returned for {city}"
                )

            if observations.get("row_count") != 7:
                raise AssertionError(
                    f"Expected 7 observations for {city}"
                )

            if observations.get("sha256_verified") is not True:
                raise AssertionError(
                    f"SHA-256 verification failed for {city}"
                )

            print(f"PASS: {city.title()} observations verified")

        query = urlencode({
            "city1": "chennai",
            "city2": "london",
            "start": "2025-07-01",
            "end": "2025-07-07",
            "metric": "temp_max_c",
        })

        _, _, response_body = get(
            base + "/api/compare?" + query
        )

        comparison = json.loads(response_body)

        if len(comparison.get("points", [])) != 7:
            raise AssertionError(
                "Expected 7 comparison data points"
            )

        print("PASS: Cross-region comparison verified")
    if hosting_only:
        from urllib.parse import urlencode
        query = urlencode({"city": "chennai", "start": "2025-01-01", "end": "2025-01-02"})
        try:
            get(base + "/api/observations?" + query)
        except HTTPError as exc:
            body = json.loads(exc.read().decode("utf-8"))
            if exc.code != 503 or body.get("error", {}).get("code") != "DATA_NOT_CONNECTED":
                raise AssertionError("Hosting-only data endpoint returned incorrect error") from exc
        else:
            raise AssertionError("Hosting-only data endpoint incorrectly returned data")
        print("PASS: hosting-only mode blocks environmental data access")
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="CloudFormation WebsiteUrl")
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
