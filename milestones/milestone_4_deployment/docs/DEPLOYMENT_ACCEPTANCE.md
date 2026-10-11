# EnviroSync M4A — AWS Free plan acceptance checklist

Hosting only: **no environmental data buckets accessed**, even if local `.env` contains bucket names.

| ID | Live/offline check | Expected outcome |
| --- | --- | --- |
| F01 | `aws freetier get-account-plan-state --region us-east-1` | `FREE`, `ACTIVE`, positive credits, unexpired plan |
| F02 | Deployment is in `ap-south-1` | No London-region AWS infrastructure; no S3 Cross-Region Replication |
| F03 | CloudFormation template review | Lambda has no policies granting access to India or London dataset buckets |
| F04 | Browser `WebsiteUrl` | React shell over HTTPS, no local terminal |
| F05 | `GET /api/health` | HTTP 200, JSON `status=ok`, `aws_checked=false` |
| F06 | `GET /api/datasets` | HTTP 200, `{"schema_version":"1.0","datasets":[]}` without AWS calls |
| F07 | `GET /api/observations` and `/api/compare` | HTTP 503, code `DATA_NOT_CONNECTED` |
| F08 | UI empty state | `No published datasets` and no fabricated weather observations |
| F09 | Private React website bucket | Block Public Access on, CloudFront OAC-only read policy |
| F10 | AWS cost guards | Free Tier credit balance checked before deployment, Lambda reserved concurrency 2, HTTP API throttling, logs retained 3 days |
| F11 | GitHub Actions | Manual `workflow_dispatch`, OIDC short-lived credentials, Free plan preflight, no stored AWS keys |

Run offline tests: `python -m pytest -q` and `npm test` from `milestones/milestone_3_frontend`.

Run live acceptance after deployment:

```powershell
.\.venv\Scripts\python.exe .\milestones\milestone_4_deployment\scripts\check_live_hosting.py --url https://YOUR_REAL_CLOUDFRONT_DOMAIN --expect-empty --hosting-only
```

**Do not claim M4A accepted without an actual AWS deployment and successful live URL checks.** Tests are not a substitute for the real account's service permission/quota validation. M4B (data federation) is separate.
