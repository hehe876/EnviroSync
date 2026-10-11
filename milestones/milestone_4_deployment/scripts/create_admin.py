"""Create or finish provisioning one Cognito administrator without logging secrets.

This script makes real AWS changes; run only after confirming costs and account.
"""
import argparse
import getpass
import re

import boto3
from botocore.exceptions import ClientError

STACK_NAME = "envirosync-admin-auth"
REGION = "ap-south-1"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Administrator email address")
    parser.add_argument("--stack", default=STACK_NAME)
    args = parser.parse_args()

    email = args.email.strip().lower()
    if not re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email):
        parser.error("Specify a valid administrator email")

    session = boto3.Session(region_name=REGION)
    account = session.client("sts").get_caller_identity()["Account"]
    print(f"AWS account: {account}")
    confirmation = input("Type the account ID to confirm creation in THIS account: ").strip()
    if confirmation != account:
        raise SystemExit("Account confirmation does not match. No changes made.")

    response = session.client("cloudformation").describe_stacks(StackName=args.stack)
    outputs = {o["OutputKey"]: o["OutputValue"] for o in response["Stacks"][0].get("Outputs", [])}
    pool_id = outputs.get("UserPoolId")
    if not pool_id:
        raise SystemExit("Could not find Cognito UserPoolId in the auth stack")

    password = getpass.getpass("Administrator password (14+ chars, upper/lower/number/symbol): ")
    again = getpass.getpass("Confirm password: ")
    if password != again or len(password) < 14 or not all([
        re.search(r"[a-z]", password), re.search(r"[A-Z]", password),
        re.search(r"[0-9]", password), re.search(r"[^A-Za-z0-9]", password),
    ]):
        raise SystemExit("Password confirmation or complexity policy failed. No changes made.")
    del again

    print("Creating user with invite email suppressed. TOTP MFA is required during Cognito sign-in.")
    cognito = session.client("cognito-idp")
    try:
        cognito.admin_create_user(
            UserPoolId=pool_id,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
            MessageAction="SUPPRESS",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "UsernameExistsException":
            raise
        print("User already exists; finishing password/group configuration.")

    cognito.admin_set_user_password(UserPoolId=pool_id, Username=email, Password=password, Permanent=True)
    del password
    cognito.admin_add_user_to_group(UserPoolId=pool_id, Username=email, GroupName="envirosync-admin")
    print("PASS: Administrator provisioned. Sign in via the website to enroll TOTP MFA.")
    print("No password or access token was written to a file or printed.")


if __name__ == "__main__":
    main()
