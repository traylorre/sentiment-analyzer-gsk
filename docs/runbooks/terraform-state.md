# Runbook: Terraform state, locks, and backend setup

> **CANON**: verified against code.

Load this when a terraform run is blocked, or when setting up state on a fresh clone. Not needed
in normal work.

## Backend layout

An **S3 backend using partial configuration**, so preprod and prod state stay separate.
`infrastructure/terraform/main.tf` declares only `encrypt = true`; the bucket and key come from
`backend-preprod.hcl` and `backend-prod.hcl`.

Both environments live in the **same bucket**, separated only by key
(`preprod/terraform.tfstate`, `prod/terraform.tfstate`). A wrong key or a wrong bucket path hits
the other environment.

Initialize with the environment's config, never bare, and always with both extra flags:

```bash
cd infrastructure/terraform
terraform init \
  -backend-config=backend-preprod.hcl \
  -backend-config="region=${AWS_REGION}" \
  -reconfigure
```

Neither `.hcl` file sets `region`; both say so in a comment, and all three CI init calls pass it as
a second `-backend-config`. Omit it and init depends on ambient config.

**`-reconfigure` is not optional.** On a working copy already initialized for one environment,
`terraform init` with the other environment's `.hcl` and no `-reconfigure` exits with
`Error: Backend configuration changed` (Terraform 1.9.8). Under `-migrate-state` it instead offers
to copy the cached environment's state into the new backend, and accepting writes one
environment's state under the other's key. `-reconfigure` switches backend without migrating.

Before acting on any state, confirm which backend you are actually pointed at:

```bash
terraform state pull > /tmp/state-backup.json   # keep this, it is your rollback
python3 -c "import json;d=json.load(open('.terraform/terraform.tfstate'));print(d['backend']['config'])"
```

Bare `terraform init` cannot complete on a **fresh clone**, where `main.tf` carries no bucket name:
with `-input=false` it exits on `Missing Required Value` for `bucket` and `key`, and without it
(the `Makefile:295` form) it prompts for them at the terminal. On a directory that has already
been initialized it **succeeds silently against the last-used backend**, which is the dangerous
case, not the safe one. Three committed callers do exactly this: `Makefile:295` (`tf-init`),
`import-existing.sh:40`, and `infrastructure/scripts/deploy.sh:136`. There is no `dev` backend config, so
anything defaulting to `dev` lands on whichever backend was cached.

## State locking is not configured

Bootstrap scripts and older docs describe S3 native `.tflock` locking. `use_lockfile` is set in no
backend block, and there is no DynamoDB lock table (`bootstrap/main.tf` creates the state bucket
only). Treat concurrent runs as unprotected: **do not run terraform locally while CI is
deploying.**

The CI pipeline's own protection is a GitHub Actions `concurrency` group, one deploy at a time.

## If a run reports a stale lock

**This cannot happen in the current configuration, and the usual remedies are no-ops.** With no
locking backend there is no lock for `force-unlock` to clear, and Terraform never writes a
`.tflock` object, so `aws s3 rm ...tflock` deletes nothing (or, with one typo, deletes live state).
Do not run either against the state bucket.

What produces lock-shaped noise anyway:

- `deploy.yml:873` and `:2018` run a "Check for Stale Terraform Locks" step that looks up
  (`aws s3api head-object`) a `.tflock` that can never be written, and every CI `refresh`, `plan`
  and `apply` passes `-lock-timeout=5m`. That messaging is dead code. Do not go hunting a `LOCK_ID` out of it.
- `backend-preprod.hcl:14`, `bootstrap-preprod.sh:38` and `bootstrap-prod.sh:59` all still claim
  native locking is enabled. They are wrong; see the section above.

A real symptom here is two writers clobbering each other, not a lock. Recover from S3 versioning,
which `bootstrap/main.tf:59-65` enables on the state bucket and which is the only server-side
rollback path this setup has:

```bash
BUCKET=$(grep '^bucket' backend-preprod.hcl | cut -d'"' -f2)
aws s3api list-object-versions --bucket "$BUCKET" --prefix preprod/terraform.tfstate \
  --query 'Versions[].[VersionId,LastModified]' --output text
```

Get the bucket name from `backend-preprod.hcl` rather than hardcoding it.

## Other writers of this state

The CI `concurrency` group protects deploys from each other. It gives **zero** protection against a
local run. These all write state and none is covered:

- `.github/workflows/deploy.yml:930` runs `terraform refresh` in `deploy-preprod`, and `:2073` does
  the same in `deploy-prod`. Each is a write.
- `Makefile:300` (`tf-plan`) and `:312` (`tf-destroy`) pass `environment=$(ENV)`, which defaults to
  `dev` (`ENV ?= dev`, `Makefile:11`). `tf-apply` (`:306`) applies whatever `tfplan` holds, and
  `tf-init` (`:294`) is a bare init. On a checkout initialized for preprod, `make tf-destroy` plans
  a destroy against **preprod state** with dev variable values.
- `infrastructure/scripts/deploy.sh` runs a bare `terraform init -input=false` (`:136`), creates or
  selects a workspace named for its argument (`:139`), then plans and applies (`:158`, `:161`)
  against whatever backend was cached.
- `import-existing.sh` hardcodes `ENVIRONMENT="dev"` (`:19`) and runs a bare
  `terraform init -input=false` (`:40`), so its `terraform import` calls at `:57` write
  **dev-named physical resources into whatever backend was cached**, normally preprod. See the
  warning in the import section below before running it.

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

`infrastructure/terraform/import-existing.sh` imports three of the eight secrets (`tiingo`,
`finnhub`, `dashboard_api_key`). Add the rest by hand if a run needs them.

**Do not run it as-is.** `:19` hardcodes `ENVIRONMENT="dev"`, `:20` hardcodes
`AWS_REGION="us-east-1"`, and `:40` is a bare `terraform init` with no `-backend-config`. It
therefore adopts the cached backend, which on any working copy used for preprod is
`preprod/terraform.tfstate`, and writes dev-named resources into it. Re-init explicitly with
`-reconfigure` first, and take a `terraform state pull` backup, or edit the script's environment
before invoking it.

## Secret population

Terraform creates the `tiingo`, `finnhub`, and `dashboard-api-key` secrets EMPTY; only the OAuth
secrets get placeholder versions (`modules/secrets/main.tf:229`, `:257`, both with
`ignore_changes`). Values are populated manually after apply, so a fresh environment serves 500s
until someone does.
