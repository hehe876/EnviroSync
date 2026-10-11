from datetime import date, timedelta
from io import BytesIO

import pytest

from milestones.milestone_1b_federation.config import Settings


@pytest.fixture
def settings(tmp_path, monkeypatch):
    for variable in ("INDIA_BUCKET", "LONDON_BUCKET", "INDIA_REGION", "LONDON_REGION"):
        monkeypatch.delenv(variable, raising=False)
    env = tmp_path / ".env"
    env.write_text("INDIA_BUCKET=envirosync-chennai-test123\nLONDON_BUCKET=envirosync-london-test123\nINDIA_REGION=ap-south-1\nLONDON_REGION=eu-west-2\n", encoding="utf-8")
    return Settings(env)


def sample_api_payload(first="2025-07-01", n=3, timezone="Asia/Kolkata"):
    beginning = date.fromisoformat(first)
    return {
        "timezone": timezone,
        "daily_units": {"temperature_2m_max": "°C", "temperature_2m_min": "°C", "precipitation_sum": "mm"},
        "daily": {
            "time": [(beginning + timedelta(days=i)).isoformat() for i in range(n)],
            "temperature_2m_max": [30 + i for i in range(n)],
            "temperature_2m_min": [20 + i for i in range(n)],
            "precipitation_sum": [float(i) for i in range(n)],
        },
    }


class FakeS3:
    def __init__(self, region, objects):
        self.region = region
        self.objects = objects

    def head_bucket(self, Bucket):
        return {"ResponseMetadata": {"HTTPHeaders": {"x-amz-bucket-region": self.region}}}

    def put_object(self, Bucket, Key, Body, ContentType, ServerSideEncryption):
        assert ContentType == "application/json"
        assert ServerSideEncryption == "AES256"
        self.objects[(self.region, Bucket, Key)] = Body
        return {"ETag": "mock-etag"}

    def get_object(self, Bucket, Key):
        key = (self.region, Bucket, Key)
        if key not in self.objects:
            raise ValueError("Fake S3 object not found")
        raw = self.objects[key]
        return {"Body": BytesIO(raw), "ContentLength": len(raw)}


class FakeSession:
    def __init__(self):
        self.objects = {}
        self.regions = []

    def client(self, service, region_name, config):
        assert service == "s3"
        self.regions.append(region_name)
        return FakeS3(region_name, self.objects)


@pytest.fixture
def fake_session():
    return FakeSession()
