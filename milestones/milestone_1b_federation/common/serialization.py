"""Canonical JSON for checksum-stable S3 objects and catalog content."""
import json

def to_json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")) + "\n").encode("utf-8")
