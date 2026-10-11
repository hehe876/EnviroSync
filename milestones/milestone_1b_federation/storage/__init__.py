"""Storage adapters; importing this does not contact AWS."""
from .s3 import S3ObjectStore, to_json_bytes
__all__ = ["S3ObjectStore", "to_json_bytes"]
