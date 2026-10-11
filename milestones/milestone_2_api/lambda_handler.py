"""AWS Lambda HTTP API v2 entry point; uses the canonical FastAPI app."""
from mangum import Mangum
from .app import app

handler = Mangum(app, lifespan="off")
