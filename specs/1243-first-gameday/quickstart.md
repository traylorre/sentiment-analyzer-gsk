# Quickstart: First Chaos Gameday

**Feature**: 1243-first-gameday

## What This Feature Does

Executes the first chaos gameday in preprod, validating all chaos injection scenarios, safety mechanisms, and establishing baseline reports for future comparison.

## Prerequisites

1. Feature 1240 deployed (optional but preferred for auto-report persistence)
2. Feature 1242 deployed (optional for visual report viewer)
3. Buddy operator available for full duration
4. MFA-enabled AWS credentials for preprod
5. Slack channel for team notification

## Steps

### 1. Enable chaos (one-time)
```bash
# In infrastructure/terraform/preprod.tfvars
enable_chaos_testing = true

# Review and apply
terraform plan -var-file=preprod.tfvars
terraform apply -var-file=preprod.tfvars
```

### 2. Pre-flight
```bash
scripts/chaos/status.sh preprod
# Complete preflight-checklist.md (all 8 sections)
```

### 3. Arm & Execute
```bash
aws ssm put-parameter --name /chaos/preprod/kill-switch --value armed --overwrite
# Follow gameday-runbook.md
```

### 4. Store results
```bash
mkdir -p reports/chaos/gameday-001
# Export or verify auto-persisted reports
git add reports/chaos/ && git commit -S -m "docs: First gameday baseline reports"
```

### 5. Post-mortem & disarm
```bash
aws ssm put-parameter --name /chaos/preprod/kill-switch --value disarmed --overwrite
# Complete post-mortem.md
```
