# Milestone 1A — Existing AWS S3 infrastructure

**Responsibility:** the two separately configured S3 storage regions and their security baseline.

Milestone 1A was completed outside this code package; it created and tested your actual S3 buckets.
This folder records those external infrastructure requirements **without cloning resources, inventing IAM permissions, or provisioning anything automatically**.
No AWS account IDs, access keys, bucket names, `.env` credentials, Terraform state, or billing credentials are committed.

## Expected existing resources

- Private India S3 bucket: AWS `ap-south-1` (Mumbai), `INDIA_BUCKET` in root `.env`.
- Private London S3 bucket: AWS `eu-west-2`, `LONDON_BUCKET` in root `.env`.
- Your pre-existing IAM identity with appropriate least-privilege access to only required bucket/key prefixes.
- Region and bucket names validated by Milestone 1B before publishing.

These resources are external dependencies, not Python modules; **there is no bucket-creation code** in this repository.
See `docs/EXISTING_RESOURCES.md` and the root `.env.example`.
