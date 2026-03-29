# Research: First Chaos Gameday Execution

**Feature**: 1243-first-gameday
**Date**: 2026-03-27

## R1: Terraform Enable Chaos

**Decision**: Set `enable_chaos_testing = true` in preprod.tfvars.

**Rationale**: The chaos module is already fully implemented and gated by this flag. The Terraform code has been reviewed through Features 1236-1238. This is a configuration toggle, not new infrastructure.

**What gets created**: SSM kill switch parameter, FIS execution role (placeholder), deny-dynamodb-write IAM policy, chaos-engineer IAM role, CloudWatch log group. All already defined in code.

## R2: Gameday Execution Strategy

**Decision**: Execute ingestion-resilience plan only (2 scenarios). Cold-start-resilience is stretch goal.

**Rationale**: First gameday should be conservative. Ingestion resilience covers the most critical failure modes (pipeline failure + database denial). Cold-start resilience can be a separate gameday once the first one validates the process.

**Timeline**: ~60 minutes for ingestion-resilience (10 min preflight + 30 min execution + 10 min safety + 10 min reports). Cold-start would add ~30 minutes.

## R3: Report Persistence Strategy

**Decision**: Dual approach — Feature 1240 API if available, manual JSON export as fallback.

**Rationale**: Feature 1240 may not be deployed by gameday time. Manual export (`curl + jq + commit`) provides equivalent data. The key is capturing the report JSON, not which tool stores it.

**Manual export pattern**:
```bash
REPORT=$(curl -s -H "X-API-Key: $KEY" \
  "https://$DASHBOARD_URL/chaos/experiments/$ID/report")
echo "$REPORT" | python3 -m json.tool > \
  "reports/chaos/gameday-001/ingestion-failure-$(date +%Y-%m-%d).json"
```

## R4: Safety Mechanism Selection

**Decision**: Test kill switch first (lowest risk), then andon cord if time permits.

**Rationale**: Kill switch test is non-destructive — it just prevents new injections. Andon cord test restores everything, which is useful at gameday end. Auto-restore Lambda test requires a real alarm to fire, which happens naturally during scenarios.

## R5: Post-Mortem Format

**Decision**: Structured markdown document in `reports/chaos/gameday-001/post-mortem.md`.

**Rationale**: Committed to repo for historical reference. Follows the questions from chaos plan YAML post_mortem section. Includes assertion results table for quick reference.
