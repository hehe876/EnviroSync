"""Stable API error contract and exception handlers."""
import logging
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from botocore.exceptions import BotoCoreError, ClientError

log = logging.getLogger("milestones.milestone_2_api")
class ApiProblem(Exception):
    def __init__(self, status, code, message):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def error_response(status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})



async def handle_api_problem(request: Request, exc: ApiProblem):
    return error_response(exc.status, exc.code, exc.message)

async def handle_invalid_request(request: Request, exc: RequestValidationError):
    return error_response(422, "INVALID_QUERY", "One or more required query parameters are missing or invalid. Check /docs.")

async def handle_aws_error(request: Request, exc: ClientError):
    code = str(exc.response.get("Error", {}).get("Code", "Unknown"))
    log.warning("AWS S3 operation failed with code %s", code)
    return error_response(502, "AWS_REQUEST_FAILED", "S3 retrieval failed. Verify IAM access, published objects and AWS connectivity.")

async def handle_botocore_error(request: Request, exc: BotoCoreError):
    log.warning("AWS SDK request failed: %s", type(exc).__name__)
    return error_response(503, "AWS_UNAVAILABLE", "AWS is unavailable or credentials could not be obtained. Check the configured AWS profile.")

async def handle_invalid_dataset(request: Request, exc: ValueError):
    log.warning("Data validation failed: %s", str(exc))
    return error_response(502, "INVALID_REMOTE_DATA", "Published S3 catalog or dataset failed validation or integrity checks. Run the Milestone 1B verify command.")
