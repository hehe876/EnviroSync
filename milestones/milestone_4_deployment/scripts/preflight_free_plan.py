"""Read-only account-plan preflight for EnviroSync's AWS Free hosting release.

Requires AWS CLI v2, permission freetier:GetAccountPlanState and sts:GetCallerIdentity.
Stops before any stack changes when the plan cannot be verified as ACTIVE/FREE.
"""
import argparse
from datetime import datetime, timezone
import json
import subprocess
import sys


def aws_json(*args):
    process = subprocess.run(
        ["aws", *args, "--output", "json", "--no-cli-pager"],
        capture_output=True, text=True, check=False,
    )
    if process.returncode:
        error = (process.stderr or process.stdout).strip()
        raise RuntimeError(f"AWS CLI failed ({' '.join(args)}): {error}")
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AWS CLI did not return JSON") from exc


def check(account, plan, now=None):
    """Pure safety validation: return a summary; raise on any ambiguous status."""
    if not isinstance(account, dict) or not isinstance(plan, dict):
        raise ValueError("Account and Free Tier response must be JSON objects")
    if account.get("Account") != plan.get("accountId"):
        raise ValueError("STS account does not match the Free Tier account")
    if plan.get("accountPlanType") != "FREE" or plan.get("accountPlanStatus") != "ACTIVE":
        raise ValueError("Deployment requires an ACTIVE AWS Free account plan")
    credits = plan.get("accountPlanRemainingCredits", {})
    if credits.get("unit") != "USD" or not isinstance(credits.get("amount"), (int, float)):
        raise ValueError("Cannot verify Free Tier credit balance")
    amount = float(credits["amount"])
    if not (0 < amount < float("inf")):
        raise ValueError("Free Tier credits are exhausted or invalid")
    expiration = plan.get("accountPlanExpirationDate")
    if not isinstance(expiration, str) or not expiration:
        raise ValueError("Free Tier plan expiration was not returned")
    try:
        ends = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid Free Tier plan expiration date") from exc
    if ends.tzinfo is None:
        raise ValueError("Plan expiration date must include a UTC offset")
    now = now or datetime.now(timezone.utc)
    if ends <= now:
        raise ValueError("AWS Free account plan is expired")
    return {"account": account["Account"], "plan": "FREE / ACTIVE", "credits_usd": round(amount, 2), "expires_at": ends.isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="ap-south-1")
    args = parser.parse_args()
    if args.region != "ap-south-1":
        print("FAIL: M4A is intentionally pinned to ap-south-1 (Mumbai)", file=sys.stderr)
        return 1
    try:
        identity = aws_json("sts", "get-caller-identity")
        # FreeTier is a global account API hosted in us-east-1.
        plan = aws_json("freetier", "get-account-plan-state", "--region", "us-east-1")
        result = check(identity, plan)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"FAIL: AWS Free plan verification: {exc}", file=sys.stderr)
        print("No changes made. Update AWS CLI and grant read-only freetier:GetAccountPlanState if needed.", file=sys.stderr)
        return 1
    print("PASS: Verified AWS Free account plan")
    print(json.dumps(result, indent=2))
    print("NOTE: Supported services can consume credits; the plan ends at the shown expiration date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
