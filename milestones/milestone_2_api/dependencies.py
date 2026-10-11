"""Dependency injection boundary for web handlers, fake tests and local AWS sessions."""
import os
from functools import lru_cache
from milestones.milestone_1b_federation.config import Settings
from milestones.milestone_1b_federation.federation import S3Federation
from .errors import ApiProblem

def hosting_only():
    """True only for the explicitly configured, S3-independent M4A release."""
    return os.getenv("ENVIROSYNC_HOSTING_ONLY", "false").strip().lower() == "true"


@lru_cache(maxsize=1)
def get_federation():
    # The M4A deployment must never initialize Boto3 or access any regional bucket.
    if hosting_only():
        return None
    try:
        return S3Federation(Settings())
    except ValueError as exc:
        raise ApiProblem(503, "CONFIGURATION_ERROR", "Backend S3 configuration is invalid. Check the local .env file.") from exc
