# Terraform Backend Bootstrap

> **CANON**: verified against code.

Creates the S3 bucket that holds Terraform state. Run once per AWS account.

Operational procedure (stale locks, force-unlock, importing secrets) is in
`docs/runbooks/terraform-state.md`.

## One-Time Setup

```bash
cd infrastructure/terraform/bootstrap
terraform init
terraform apply -var aws_region=<region>
terraform output state_bucket_name
```

`aws_region` has no default and must be passed.

Put the resulting bucket name into `backend-preprod.hcl` and `backend-prod.hcl`, then initialize
the main configuration with the environment's partial config:

```bash
cd infrastructure/terraform
terraform init -backend-config=backend-preprod.hcl
```

Bare `terraform init` fails there: `main.tf` declares only `encrypt = true` and carries no bucket
name.

## Resources Created

- **S3 Bucket**: `sentiment-analyzer-terraform-state-<account-id>`
  - Versioning enabled for state history
  - Server-side encryption (AES256)
  - Public access blocked
  - `prevent_destroy` lifecycle guard

Nothing else. There is no lock table, and `use_lockfile` is set in no backend block, so concurrent
runs are unprotected. Do not run terraform locally while CI is deploying.
