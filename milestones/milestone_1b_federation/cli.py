"""Command-line interface for ingestion, publication, discovery and verification."""

import argparse
import json
from pathlib import Path
import sys

from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, PartialCredentialsError

from .federation import S3Federation
from .config import Settings
from .ingestion import parse_interval
from .ingestion.local import fetch_both, load_prepared


def print_json(value):
    print(json.dumps(value, indent=2, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description="EnviroSync modular ingestion and S3 federation")
    parser.add_argument("--env", default=".env", help="Path to the existing Milestone 1A .env")
    commands = parser.add_subparsers(dest="command", required=True)

    for command in ("fetch", "publish"):
        sub = commands.add_parser(command)
        sub.add_argument("--start", default="2024-01-01")
        sub.add_argument("--end", default="2025-12-31")
        sub.add_argument("--output-dir", default="milestones/milestone_1b_federation/preview")
        if command == "publish":
            sub.add_argument("--confirm-aws-charges", action="store_true", required=True,
                             help="Acknowledge that S3 calls may incur charges even on an older Free Tier account")

    commands.add_parser("discover")
    commands.add_parser("verify")
    reader = commands.add_parser("read")
    reader.add_argument("--city", choices=["chennai", "london"], required=True)
    reader.add_argument("--start")
    reader.add_argument("--end")
    reader.add_argument("--limit", type=int, default=5)
    compare = commands.add_parser("compare")
    compare.add_argument("--start", default="2025-07-01")
    compare.add_argument("--end", default="2025-07-07")

    args = parser.parse_args(argv)
    try:
        settings = Settings(args.env)
        if args.command == "fetch":
            fetch_both(settings, args.start, args.end, args.output_dir)
            print("LOCAL PREVIEW ONLY. No AWS requests were made by this command.")
            return 0
        if args.command == "publish":
            data = load_prepared(settings, args.start, args.end, args.output_dir)
            federation = S3Federation(settings)
            catalog = federation.publish(data)
            print("Published regional datasets and Mumbai catalog:")
            print_json({"catalog_bucket": settings.catalog_bucket,
                        "catalog_key": "envirosync/v1/catalog/datasets.json",
                        "datasets": catalog["datasets"]})
            print("Run 'python -m milestones.milestone_1b_federation.cli verify' next.")
            return 0

        federation = S3Federation(settings)
        if args.command == "discover":
            print_json(federation.discover())
        elif args.command == "verify":
            rows = []
            for name in settings.cities:
                result = federation.retrieve(name)
                rows.append({"city": name, "region": result["region"], "bucket": result["bucket"],
                             "observations": result["total_records"], "sha256_verified": result["sha256_verified"]})
            print_json({"status": "PASS", "regional_datasets": rows})
        elif args.command == "read":
            if args.limit < 1 or args.limit > 100:
                raise ValueError("--limit must be between 1 and 100")
            result = federation.retrieve(args.city, args.start, args.end)
            result["observations"] = result["observations"][:args.limit]
            result["displayed_records"] = len(result["observations"])
            print_json(result)
        elif args.command == "compare":
            first, last = parse_interval(args.start, args.end)
            if (last - first).days > 30:
                raise ValueError("CLI comparison is limited to at most 31 days")
            data = {name: federation.retrieve(name, args.start, args.end) for name in settings.cities}
            a = {x["date"]: x for x in data["chennai"]["observations"]}
            b = {x["date"]: x for x in data["london"]["observations"]}
            aligned = []
            for day in sorted(set(a) & set(b)):
                aligned.append({"date": day, "chennai_max_temp_c": a[day]["max_temp_c"],
                                "london_max_temp_c": b[day]["max_temp_c"],
                                "difference_c": round(a[day]["max_temp_c"] - b[day]["max_temp_c"], 2)})
            if not aligned:
                raise ValueError("No matching dates between the regional datasets")
            print_json({"start": args.start, "end": args.end,
                        "source_regions": [data["chennai"]["region"], data["london"]["region"]],
                        "aligned_days": len(aligned), "comparisons": aligned})
        return 0
    except (ValueError, RuntimeError, ClientError, BotoCoreError, NoCredentialsError, PartialCredentialsError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
