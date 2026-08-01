# Runbook: Terraform state, locks, and backend setup

Load this when a terraform run is blocked, or when setting up state on a fresh clone. Not needed
in normal work.

## Backend layout

An **S3 backend using partial configuration**, so preprod and prod state stay separate.
`infrastructure/terraform/main.tf` declares only `encrypt = true`; the bucket and key come from
`backend-preprod.hcl` and `backend-prod.hcl`.

Initialize with the environment's config, never bare:

```bash
cd infrastructure/terraform
terraform init -backend-config=backend-preprod.hcl   # or backend-prod.hcl
```

Bare `terraform init` prompts or fails, because `main.tf` carries no bucket name. There is no
`dev` backend config.

## State locking is not configured

Bootstrap scripts and older docs describe S3 native `.tflock` locking. `use_lockfile` is set in no
backend block, and there is no DynamoDB lock table (`bootstrap/main.tf` creates the state bucket
only). Treat concurrent runs as unprotected: **do not run terraform locally while CI is
deploying.**

The CI pipeline's own protection is a GitHub Actions `concurrency` group, one deploy at a time.

## If a run reports a stale lock

```bash
cd infrastructure/terraform
terraform init -backend-config=backend-preprod.hcl
terraform force-unlock <LOCK_ID>     # Lock ID is in the error or the workflow log
```

Or remove the lock object directly:

```bash
aws s3 rm s3://<state-bucket>/preprod/terraform.tfstate.tflock
aws s3 rm s3://<state-bucket>/prod/terraform.tfstate.tflock
```

Check whether one exists:

```bash
aws s3api head-object --bucket <state-bucket> --key preprod/terraform.tfstate.tflock
```

Get the bucket name from `backend-preprod.hcl` rather than hardcoding it.

## Fresh bootstrap

```bash
cd infrastructure/terraform/bootstrap
terraform init && terraform apply
terraform output state_bucket_name
```

`aws_region` has no default and must be passed. Full procedure is in
`infrastructure/terraform/bootstrap/README.md`.

## Importing existing secrets

`infrastructure/terraform/modules/secrets/main.tf` defines `dashboard_api_key`, `tiingo`,
`finnhub`, `sendgrid`, `hcaptcha`, `stripe_webhook`, `google_oauth`, `github_oauth`.

There is **no `newsapi` secret**. Any import instruction naming
`module.secrets.aws_secretsmanager_secret.newsapi` will fail.

`infrastructure/terraform/import-existing.sh` imports three of the eight secrets. Add the rest by
hand if a run needs them.
