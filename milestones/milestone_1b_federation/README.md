# Milestone 1B — Environmental data federation (Python block)

**Owns:** validated historical Open-Meteo ERA5 ingestion, normalized local JSON, region-specific S3 adapter, global manifest catalog, federated retrieval, SHA-256 integrity checks and CLI.

## Internal functional submodules

- `config/` — cities, regions, bucket identifiers, allowed object keys; config validation.
- `ingestion/` — fetch historical Open-Meteo daily weather, normalize and validate, write local previews.
- `storage/` — region-aware Boto3 client, bounded private S3 GET/PUT, SSE-S3 on publish.
- `catalog/` — write/validate the global catalog with an allowlist of approved bucket/region/key locations.
- `federation/` — compose catalog + S3 + dataset validation into publish, discover and retrieve operations.
- `common/` — deterministic JSON bytes for SHA-256 verification.
- `cli.py` — human-driven commands; only `publish` writes to AWS; requires explicit `--confirm-aws-charges`.
- `tests/` — per-block offline tests, using in-memory fake S3; no AWS access required.
- `examples/` — preserved original **historical** data JSON samples, not substitutes for live S3.
- `docs/historical/` — original educational reference; previous paths, not runnable setup.

## Commands (run from repository root)

```powershell
.\.venv\Scripts\python.exe -m milestones.milestone_1b_federation.cli --help
.\.venv\Scripts\python.exe -m pytest milestones/milestone_1b_federation/tests -v
# Optional real environmental API requests; no AWS writes:
.\.venv\Scripts\python.exe -m milestones.milestone_1b_federation.cli fetch --start 2025-07-01 --end 2025-07-03
```

For live AWS queries, first complete `docs/SETUP_WINDOWS.md` and verify billing and IAM. `verify` and `discover` make real AWS read requests. **Do not publish without checking data and costs.**
