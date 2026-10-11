# Migration map from previous milestone packages

The earlier milestone deliveries bundled duplicate `enviro_sync` implementations. This repository contains exactly **one** Milestone 1B implementation and one API implementation. No original AWS resources or secrets are copied into source.

| Previous location | Current location | Action |
|---|---|---|
| `src/enviro_sync/config/` | `milestones/milestone_1b_federation/config/` | Moved; rewritten imports |
| `src/enviro_sync/common/` | `milestones/milestone_1b_federation/common/` | Moved |
| `src/enviro_sync/ingestion/` | `milestones/milestone_1b_federation/ingestion/` | Moved |
| `src/enviro_sync/storage/` | `milestones/milestone_1b_federation/storage/` | Moved |
| `src/enviro_sync/catalog/` | `milestones/milestone_1b_federation/catalog/` | Moved |
| `src/enviro_sync/federation/` | `milestones/milestone_1b_federation/federation/` | Moved |
| `src/enviro_sync/cli.py` | `milestones/milestone_1b_federation/cli.py` | Moved; preview path default now inside block |
| `src/enviro_sync/api/` | `milestones/milestone_2_api/` | Moved; imports point to Milestone 1B |
| `frontend/` | `milestones/milestone_3_frontend/` | Moved entire React/Vite application |
| `tests/test_weather.py`, `tests/test_federation.py`, `tests/test_cli_and_safety.py` | `milestones/milestone_1b_federation/tests/` | Moved |
| `tests/test_api.py`, `tests/test_modular_integration.py` | `milestones/milestone_2_api/tests/` | Moved; added 3 block-architecture tests |
| `tests/conftest.py` | `conftest.py` | Shared offline test fixtures (only shared test file) |
| `data/examples/` | `milestones/milestone_1b_federation/examples/` | Preserved verified sample datasets |
| Previous PDF/Markdown code reference docs | each block's `docs/historical/` | Preserved but explicitly marked outdated commands |

**Changed Python entry points:**

- `python -m enviro_sync.cli` → `python -m milestones.milestone_1b_federation.cli`
- `uvicorn enviro_sync.api:app` → `uvicorn milestones.milestone_2_api:app`
- Any custom imports of `enviro_sync.*` must be updated to `milestones.milestone_1b_federation.*` or `milestones.milestone_2_api.*`.

**Keep your original directory as a backup until verified.** To migrate your actual AWS settings, manually copy only your existing valid bucket values to new root `.env`; leave old `.venv`, `.git`, local cache and downloaded data behind unless explicitly required. Publishing against existing keys can overwrite S3 objects and cost money; it is **never** part of offline setup.
