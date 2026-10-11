"""Region-aware private S3 adapter with strict object size and SSE-S3 safeguards."""
import boto3
from botocore.config import Config
from milestones.milestone_1b_federation.config import MAX_JSON_BYTES
from milestones.milestone_1b_federation.common import to_json_bytes

class S3ObjectStore:
    """Small adapter to keep Boto3 isolated from catalog/API logic."""
    def __init__(self, session=None):
        self.session = session if session is not None else boto3.session.Session()
        self.clients = {}

    def client(self, region):
        if region not in self.clients:
            config = Config(connect_timeout=10, read_timeout=30, retries={"mode": "standard", "max_attempts": 3})
            self.clients[region] = self.session.client("s3", region_name=region, config=config)
        return self.clients[region]

    def verify_region(self, bucket, expected_region):
        response = self.client(expected_region).head_bucket(Bucket=bucket)
        observed = response.get("BucketRegion") or response.get("ResponseMetadata", {}).get("HTTPHeaders", {}).get("x-amz-bucket-region")
        if observed != expected_region:
            raise ValueError(f"Bucket {bucket} is in {observed!r}, expected {expected_region!r}; refusing to publish")

    def get_bytes(self, region, bucket, key):
        response = self.client(region).get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        try:
            announced = response.get("ContentLength", 0)
            if announced > MAX_JSON_BYTES:
                raise ValueError(f"Refusing to download oversized object: {key}")
            raw = body.read(MAX_JSON_BYTES + 1)
            if len(raw) > MAX_JSON_BYTES:
                raise ValueError(f"S3 object exceeds {MAX_JSON_BYTES} bytes: {key}")
            return raw
        finally:
            body.close()

    def put_bytes(self, region, bucket, key, content):
        if len(content) > MAX_JSON_BYTES:
            raise ValueError(f"Refusing to upload oversized object: {key}")
        self.client(region).put_object(
            Bucket=bucket, Key=key, Body=content,
            ContentType="application/json", ServerSideEncryption="AES256",
        )

