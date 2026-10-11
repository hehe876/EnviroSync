"""HTTP composition root. Only this module builds the FastAPI app."""
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from .routes import router
from .errors import (ApiProblem, handle_api_problem, handle_invalid_request,
                     handle_aws_error, handle_botocore_error, handle_invalid_dataset)

app = FastAPI(
    title="EnviroSync Federation API",
    version="2.1.0",
    description="Local read-only REST gateway for separately regioned private S3 environmental datasets.",
    docs_url="/docs",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Accept", "Content-Type"],
)
app.add_exception_handler(ApiProblem, handle_api_problem)
app.add_exception_handler(RequestValidationError, handle_invalid_request)
app.add_exception_handler(ClientError, handle_aws_error)
app.add_exception_handler(BotoCoreError, handle_botocore_error)
app.add_exception_handler(ValueError, handle_invalid_dataset)
app.include_router(router)
