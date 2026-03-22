# Research: Chaos Injection End-to-End Wiring

**Feature Branch**: `1236-chaos-injection-wiring`
**Created**: 2026-03-21

## Decision 1: Defer dynamodb_throttle Scenario

### Context

The `dynamodb_throttle` scenario was designed to use AWS Fault Injection Service (FIS) to inject throttling on DynamoDB writes. The infrastructure code references FIS templates (`FIS_DYNAMODB_THROTTLE_TEMPLATE` env var) and the chaos module has full FIS client integration (start, stop, get status).

### Problem

The AWS Terraform provider has a known bug that prevents creating FIS experiment templates targeting DynamoDB tables. The `aws_fis_experiment_template` resource does not properly support the `aws:dynamodb:table` target type, causing `terraform apply` to fail.

### Options Evaluated

| Option | Pros | Cons |
|--------|------|------|
| **A. Use AWS FIS (blocked)** | Real AWS-level throttling, realistic simulation | Terraform provider bug blocks deployment |
| **B. App-level DynamoDB delay injection** | No Terraform changes needed | Requires modifying DynamoDB write paths in 2+ Lambdas, blast radius control is complex, not realistic (delay != throttle) |
| **C. Defer dynamodb_throttle, focus on scenarios 1+2** | Smallest scope, unblocks other scenarios, FIS can be revisited when provider is fixed | dynamodb_throttle remains unusable |

### Decision

**Option C: Defer.** The `dynamodb_throttle` scenario remains in "pending" state. The FIS integration code stays in place (no removal). When the Terraform provider bug is fixed, the scenario can be enabled by deploying the FIS template and the existing code will work.

### Evidence

- FIS client integration in chaos.py (lines 386-547) is complete and tested
- The `start_experiment()` call for `dynamodb_throttle` at line 581-592 already works
- Only the Terraform deployment step is blocked

---

## Decision 2: App-Level Injection vs AWS FIS

### Context

For `ingestion_failure` and `lambda_cold_start`, the system uses app-level injection (DynamoDB flag + application code check) rather than AWS FIS.

### Why App-Level Is Correct for These Scenarios

**ingestion_failure**: This scenario simulates "what happens when the ingestion pipeline stops producing articles." The goal is not to inject a specific AWS failure (like network partition or API error) -- it is to simulate the effect of ANY ingestion failure: no new articles flow to analysis. The simplest way to achieve this is to skip fetching. An AWS FIS approach would require targeting specific AWS services (e.g., blocking Secrets Manager access), which is indirect and harder to control.

**lambda_cold_start**: This scenario simulates "what happens when analysis Lambda has high cold start latency." AWS FIS does not support Lambda cold start injection natively. The `aws:lambda:invocation-add-delay` FIS action was introduced in 2024 but requires specific IAM permissions and Lambda configuration. Using `time.sleep()` at the application level achieves the same observable effect (increased p99 latency) with zero infrastructure changes.

### Tradeoff

App-level injection is less realistic than AWS-level injection because:
- The Lambda still executes normally (no actual resource contention)
- Error handling paths for real failures (timeout, OOM) are not exercised
- Blast radius control is binary (on/off per invocation, no percentage-based sampling)

These tradeoffs are acceptable for Phase 1 chaos testing. Real AWS failures can be injected in Phase 2 when FIS templates are deployable.

---

## Decision 3: Default delay_ms Value for lambda_cold_start

### Context

The `lambda_cold_start` scenario needs a `delay_ms` value to inject. This value simulates cold start overhead.

### Analysis of Real Cold Start Data

From CloudWatch metrics for the analysis Lambda (which loads the DistilBERT model):
- P50 cold start: ~1700ms
- P90 cold start: ~3200ms
- P99 cold start: ~4900ms

### Decision

Default `delay_ms = 3000` (3 seconds). This is between P50 and P90, producing a noticeable but not extreme effect. Operators can override via `parameters.delay_ms` at experiment creation time.

The value is stored in the experiment's `results.delay_ms` field, which `get_chaos_delay_ms()` reads at line 176 of `chaos_injection.py`.

---

## Decision 4: Chaos Check Placement in Ingestion Handler

### Context

The ingestion handler has multiple early-return paths:
1. Warmup check (line 177)
2. Config loading (line 214)
3. No active tickers (line 223)

### Decision

Place the chaos check after warmup (line 188) but before config loading. Rationale:
- **After warmup**: Warmup invocations should always succeed (they keep the container warm)
- **Before config**: If chaos is active, there is no reason to load API keys from Secrets Manager or scan the users table for active tickers. This avoids unnecessary AWS API calls and reduces the cost/latency of chaos-skipped invocations.

### Alternative Considered

Placing the check after config loading would allow logging more context (e.g., which tickers would have been fetched). Rejected because the added Secrets Manager and DynamoDB calls have no value when we know the invocation will be skipped.

---

## Existing Infrastructure Inventory

| Component | File | Status |
|-----------|------|--------|
| Dashboard UI | `src/lambdas/dashboard/static/chaos.html` | Complete |
| API routes (POST/GET experiments, start, stop) | `src/lambdas/dashboard/routes.py` | Complete |
| Experiment lifecycle (create, get, list, update, delete) | `src/lambdas/dashboard/chaos.py` | Complete except lambda_cold_start |
| DynamoDB table (chaos-experiments) | `infrastructure/terraform/modules/chaos/dynamodb.tf` | Complete |
| Chaos detection helper | `src/lambdas/shared/chaos_injection.py` | Complete |
| FIS integration | `src/lambdas/dashboard/chaos.py` (lines 386-547) | Complete (blocked by Terraform) |
| Existing tests | `tests/unit/test_chaos_fis.py`, `tests/unit/test_chaos_injection.py` | 1400+ lines |
| Analysis handler delay wiring | `src/lambdas/analysis/handler.py` (lines 116-126) | Complete |
| Ingestion handler chaos check | `src/lambdas/ingestion/handler.py` | **MISSING** |
