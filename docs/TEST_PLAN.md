# Offline and live acceptance tests

| Group | What it proves | Requirements |
|---|---|---|
| 1B Python unit | ERA5 normalization, local preview validation, catalog allowlist and S3 SHA-256 using fake S3 | Python dev deps, no AWS |
| 2 API | HTTP error contracts, validated query parameters, aligned series and private-bucket non-disclosure | Python dev deps, no AWS |
| API–1B negative controls | Missing catalog/region object returns error, not successful fake readings; restored state works | Python dev deps, no AWS |
| Block contract | API imports **Milestone 1B's** S3Federation rather than another copy | Python dev deps, no AWS |
| React Node utilities | request construction, error handling, dates and CSV contract | Node.js, no AWS |
| React build | JSX compiles with Vite and npm dependencies | `npm install` internet access as needed |
| Live AWS smoke | Published region metadata, cross-region data and SHA-256 via API | User's existing AWS buckets/IAM, applicable S3 costs |

From repo root run `python -m pytest -q` after an editable install; then `cd milestones/milestone_3_frontend; npm run test; npm run build` (after dependencies installed).

**Negative controls:** API `/api/health` still succeeds even if there is no catalog; `/api/datasets` must fail when catalog is absent; `/api/compare` must fail if London S3 data disappears; after republishing fake data, compare must succeed. These tests deliberately use fake S3 objects only, never the actual AWS account.

Real account tests cannot be asserted by offline CI. Manual opt-in `scripts/smoke-live-api.ps1` only issues S3 GET requests via your running API; live writes require explicit separate approval and CLI flag.
