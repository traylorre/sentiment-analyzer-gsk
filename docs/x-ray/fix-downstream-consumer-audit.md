# Task 12: Audit Downstream Consumers of Removed Systems

**Priority:** P3
**Spec FRs:** FR-018 (enforcement), edge cases
**Status:** TODO
**Depends on:** Tasks 6, 7, 9 (must know what's being removed before auditing consumers)
**Blocks:** Nothing (final cleanup task)

---

## Problem

Tasks 6, 7, and 9 remove three custom systems:
- `latency_logger.py` (custom structured logs)
- `cache_logger.py` (custom structured logs)
- `get_correlation_id()` / `generate_correlation_id()` (custom correlation IDs)

Any downstream consumer that depends on these (CloudWatch alarms, Log Insights saved queries, dashboard widgets, automated checks) will silently break.

---

## What to Audit

### 1. CloudWatch Alarms

Search all Terraform alarm configurations for references to:
- `latency_logger` field names (`event_type`, `latency_ms`, `is_cold_start`, etc.)
- `cache_logger` field names (`hit_rate`, `cache_metrics`, `trigger`, etc.)
- `correlation_id` in the old format (`{source_id}-{request_id}`)

**Files to search:**
- `infrastructure/terraform/modules/cloudwatch/main.tf`
- `infrastructure/terraform/modules/cloudwatch/alarms.tf` (if exists)
- Any `.tf` file with `aws_cloudwatch_metric_alarm`

### 2. CloudWatch Log Insights Saved Queries

Check for saved queries that reference removed fields:
- `pctile()` on latency_logger's `latency_ms` field
- `filter event_type = "cache_metrics"` on cache_logger output
- `filter correlation_id like /article#/` on old correlation ID format

**Where to find:** AWS Console > CloudWatch > Logs Insights > Saved Queries (may not be in Terraform)

### 3. CloudWatch Dashboard Widgets

Search dashboard Terraform for widgets that query removed structured log fields:

**Files to search:**
- `infrastructure/terraform/modules/cloudwatch/dashboard.tf` (if exists)
- Any `.tf` file with `aws_cloudwatch_dashboard`

### 4. Application Code

Search for any remaining references to removed functions or log field names:

```
grep -r "latency_logger" src/ tests/
grep -r "cache_logger" src/ tests/
grep -r "get_correlation_id" src/ tests/
grep -r "generate_correlation_id" src/ tests/
```

### 5. Feature 1020 Validation

Feature 1020 validates cache hit rate >80%. If any automated validation queries `cache_logger` output to verify this SLO, it must be updated to query X-Ray annotations instead.

### 6. Fail-Fast Enforcement (FR-018)

Scan all modified files from tasks 2-11 to verify:
- No `try/except` blocks wrapping X-Ray SDK calls
- No fallback logic that catches X-Ray errors and continues
- X-Ray SDK errors propagate to Lambda runtime

---

## Files to Audit

| Source | What to Search | Risk |
|--------|---------------|------|
| `infrastructure/terraform/modules/cloudwatch/` | Alarm definitions referencing removed log fields | HIGH — silent alarm breakage |
| `infrastructure/terraform/main.tf` | Dashboard widget queries | MEDIUM — operator dashboard gaps |
| `src/` | Remaining imports of removed modules | HIGH — import errors at runtime |
| `tests/` | Tests referencing removed functions | MEDIUM — test failures |
| AWS Console (manual) | Saved Log Insights queries | MEDIUM — operator workflow breakage |
| `docs/` | Documentation referencing removed systems | LOW — stale docs |

---

## Success Criteria

- [ ] Zero Terraform resources reference removed structured log field names
- [ ] Zero application code imports removed modules
- [ ] Zero tests reference removed functions
- [ ] All CloudWatch dashboard widgets updated (or confirmed unaffected)
- [ ] Feature 1020 SLO validation updated to use X-Ray annotations
- [ ] FR-018 compliance verified: no try/catch around X-Ray SDK calls in any modified file
- [ ] Documentation updated to reflect X-Ray as the single tracing system

---

## Blind Spots

1. **Non-Terraform resources**: Saved CloudWatch queries and manually created dashboard widgets are not in Terraform. These require manual AWS Console audit.
2. **External consumers**: If any external monitoring tool (Datadog, PagerDuty, Grafana) queries the removed structured log fields, it will break silently. Check integration configurations.
3. **Runbooks**: Operator runbooks that say "search CloudWatch Logs for correlation_id matching..." must be updated to say "search X-Ray traces for trace ID..."
