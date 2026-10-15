# Terraform Backend Bootstrap

> **CANON**: verified against code.

Creates the S3 bucket that holds Terraform state. Run once per AWS account.

Operational procedure (stale locks, force-unlock, importing secrets) is in
`docs/runbooks/terraform-state.md`.

## One-Time Setup

Requires Terraform 1.9.8 exactly (`required_version` in `main.tf`). From the repository root:

```bash
cd infrastructure/terraform/bootstrap
terraform init
terraform apply -var aws_region=<region>
terraform output state_bucket_name
```

`aws_region` has no default and must be passed.

Bootstrap has no backend block, so its state is a local `terraform.tfstate` in this directory,
ignored by git. `terraform output` works only in the checkout that ran the apply, and an apply
from any other checkout starts from empty state and plans to create the bucket again. Both
backend files already name `sentiment-analyzer-terraform-state-218795110243`.

For a new account, put the resulting bucket name into `backend-preprod.hcl` and
`backend-prod.hcl`. Neither file sets `region`; pass it on the command line as `deploy.yml` does.
From the repository root:

```bash
cd infrastructure/terraform
terraform init -backend-config=backend-preprod.hcl -backend-config="region=<region>" -reconfigure
```

`main.tf` declares only `encrypt = true` in its `backend "s3"` block, so bucket, key and region
all come from the partial config and the command line.

## Resources Created

- **S3 Bucket**: `sentiment-analyzer-terraform-state-<account-id>`
  - Versioning enabled for state history
  - Server-side encryption (AES256)
  - Public access blocked
  - `prevent_destroy` lifecycle guard

Nothing else. There is no lock table, and `use_lockfile` is set in no backend block, so Terraform
takes no state lock. `deploy.yml` runs serialize among themselves through its `deploy-pipeline`
concurrency group; nothing serializes a local run against CI or against another local run. Do not
run terraform locally while CI is deploying.
