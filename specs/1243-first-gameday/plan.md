# Implementation Plan: First Chaos Gameday Execution

**Branch**: `1243-first-gameday` | **Date**: 2026-03-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1243-first-gameday/spec.md`

## Summary

Execute the first chaos gameday in preprod: enable chaos infrastructure via Terraform, run pre-flight checklist, execute ingestion-resilience plan (2 scenarios), validate safety mechanisms, persist baseline reports, conduct post-mortem. Primarily operational — minimal code changes (one Terraform flag + post-mortem documentation).

## Technical Context

**Language/Version**: Bash (chaos scripts), Terraform (infrastructure), Python (report API)
**Primary Dependencies**: AWS CLI, Terraform >= 1.5, existing chaos scripts and dashboard API
**Storage**: N/A (uses existing DynamoDB tables)
**Testing**: Manual execution with real AWS resources in preprod
**Target Platform**: AWS preprod environment
**Project Type**: Operational execution with minimal code changes
**Performance Goals**: Complete within 90 minutes
**Constraints**: Requires buddy operator, MFA, non-prod only
**Scale/Scope**: 2 scenarios, 6 assertions, 1 plan

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Amendment 1.6 (No Quick Fixes) | PASS | Full speckit workflow for Terraform change |
| Amendment 1.8 (Managed Policies) | N/A | No new IAM policies |
| Amendment 1.15 (No Fallback Config) | N/A | No new configuration |
| Cost Sensitivity | PASS | No new resources beyond enabling existing module |
| Prohibited: terraform apply without review | ACKNOWLEDGED | Plan review required before apply |

## Project Structure

### Source Code (in target repo: ../sentiment-analyzer-gsk/)

```text
infrastructure/terraform/
└── preprod.tfvars          # MODIFY: Set enable_chaos_testing = true

reports/chaos/
└── gameday-001/            # NEW: First gameday baseline reports
    ├── ingestion-failure.json
    ├── dynamodb-throttle.json
    └── post-mortem.md

docs/chaos-testing/
├── gameday-runbook.md      # READ: Follow during execution
└── preflight-checklist.md  # READ: Complete before injection
```

## Implementation Phases

### Phase 1: Enable Infrastructure (pre-gameday)
- Set `enable_chaos_testing = true` in preprod.tfvars
- Run `terraform plan` — review that ONLY chaos resources are created
- Run `terraform apply` after plan review
- Verify with `scripts/chaos/status.sh preprod`

### Phase 2: Pre-Flight (10 minutes)
- Complete all 8 preflight checklist sections
- Document results with timestamps
- Arm chaos gate: `aws ssm put-parameter --name /chaos/preprod/kill-switch --value armed`
- Buddy sign-off

### Phase 3: Execute Ingestion Resilience Plan (~30 minutes)
- Scenario 1: ingestion_failure (concurrency=0, 120s, 100% blast radius)
  - Inject via dashboard API or scripts/chaos/inject.sh
  - Observe CloudWatch: Throttles, Errors, ArticlesFetched
  - Stop experiment after observation period
  - Record report and verdict
  - Wait 2+ minutes before next scenario
- Scenario 2: dynamodb_throttle (deny policy, 120s, 100% blast radius)
  - Inject via dashboard API or scripts/chaos/inject.sh
  - Observe CloudWatch: Lambda Errors, DynamoDB SystemErrors
  - Stop experiment after observation period
  - Record report and verdict

### Phase 4: Safety Mechanism Validation (~10 minutes)
- Test at least ONE of:
  - Kill switch: Set to "triggered" and verify injection blocked
  - Auto-restore: Verify Lambda fires on composite alarm
  - Andon cord: Run scripts/chaos/andon-cord.sh and verify restore
- Document PASS/FAIL for tested mechanism

### Phase 5: Baseline Reports (~10 minutes)
- If Feature 1240 deployed: Reports auto-persisted, verify via API
- If not deployed: Export reports manually via `curl GET /chaos/experiments/{id}/report`
- Create reports/chaos/gameday-001/ directory
- Save report JSON files
- Commit to repo

### Phase 6: Post-Mortem (~15 minutes)
- Review all experiment reports
- Address each assertion from ingestion-resilience.yaml (6 assertions)
- Document: actual vs expected, recovery times, alarm timing, unexpected findings
- Identify action items with owners and target dates
- Disarm chaos gate
- Notify team in Slack
