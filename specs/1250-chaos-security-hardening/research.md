# Research: Chaos Security Hardening

## R1: EventBridge Scheduler vs EventBridge Rules

**Decision**: Use EventBridge Scheduler (boto3 client `scheduler`), NOT EventBridge Rules (boto3 client `events`).

**Rationale**: EventBridge Scheduler supports `at()` one-time expressions (e.g., `at(2026-03-24T15:30:00)`) for scheduling a single invocation at a specific time. EventBridge Rules only support `rate()` and `cron()` — no one-time triggers.

**Alternatives considered**:
- EventBridge Rules with `cron()` at a specific time: Rejected — cron fires every year/month, not one-time. Would need manual cleanup.
- Step Functions Wait state: Rejected — overkill for a simple timer, adds service dependency.
- Lambda-internal `time.sleep()`: Rejected — Lambda has 15-minute max timeout, and tying up a Lambda invocation for 300 seconds wastes compute.
- DynamoDB TTL stream + Lambda trigger: Rejected — TTL deletion is eventually consistent (up to 48 hours late). Not suitable for time-critical auto-restore.

**API details**:
```python
scheduler = boto3.client("scheduler")
scheduler.create_schedule(
    Name="chaos-auto-restore-{experiment_id}",
    ScheduleExpression="at(2026-03-24T15:35:00)",
    FlexibleTimeWindow={"Mode": "OFF"},
    Target={
        "Arn": DASHBOARD_LAMBDA_ARN,
        "RoleArn": SCHEDULER_ROLE_ARN,
        "Input": json.dumps({"action": "auto-restore", "experiment_id": experiment_id}),
    },
    ActionAfterCompletion="DELETE",  # Self-cleaning one-time schedule
)
```

**Key finding**: `ActionAfterCompletion="DELETE"` makes the schedule self-deleting after it fires. No cleanup needed.

## R2: Rate Limiting Approach

**Decision**: Use DynamoDB conditional write with a per-user rate-limit item.

**Rationale**: The chaos experiments table already has user_id. Rather than querying recent experiments (eventual consistency risk), use a dedicated rate-limit item with a conditional write that atomically checks the timestamp.

**Alternatives considered**:
- DynamoDB GSI query by user_id + created_at: Rejected — GSI is eventually consistent, could miss a write from <1 second ago.
- API Gateway throttling: Rejected — chaos routes bypass API Gateway (direct Function URL).
- In-memory rate limit (functools.lru_cache): Rejected — Lambda is stateless, memory doesn't persist across invocations.
- Redis/ElastiCache: Rejected — overkill, adds infrastructure dependency.

**Critical schema note**: The chaos experiments table uses `experiment_id` (hash) + `created_at` (range) — NOT PK/SK. Rate limit and lock items reuse this table with synthetic `experiment_id` values prefixed with `RATELIMIT#` or `CHAOSLOCK#`.

**Implementation pattern**:
```python
table.put_item(
    Item={
        "experiment_id": f"RATELIMIT#chaos#{user_id}",
        "created_at": current_iso_timestamp,
        "last_created_epoch": current_timestamp,
        "ttl": current_timestamp + 120,  # Auto-cleanup after 2 minutes
    },
    ConditionExpression="attribute_not_exists(experiment_id) OR last_created_epoch < :cutoff",
    ExpressionAttributeValues={":cutoff": current_timestamp - 60},
)
```

If the condition fails (item exists AND last_created_epoch >= cutoff), a `ConditionalCheckFailedException` is raised → 429.

**Key insight**: Uses the SAME chaos experiments table with synthetic `experiment_id` values. No new table or GSI needed. TTL auto-cleans stale rate limit records.

## R3: Concurrent Experiment Prevention

**Decision**: Use DynamoDB conditional write with a per-scenario-type lock item.

**Rationale**: Same atomic conditional write pattern as rate limiting. Before starting an experiment, write a lock item that only succeeds if no lock exists for that scenario_type.

**Implementation pattern** (using experiment_id/created_at keys):
```python
# Acquire lock before starting
table.put_item(
    Item={
        "experiment_id": f"CHAOSLOCK#{scenario_type}",
        "created_at": "ACTIVE",
        "locked_experiment_id": experiment_id,
        "started_at": timestamp_iso,
        "ttl": timestamp_epoch + 600,  # Safety: auto-expire in 10 minutes
    },
    ConditionExpression="attribute_not_exists(experiment_id)",
)
# If ConditionalCheckFailedException → 409 Conflict

# Release lock when stopping
table.delete_item(Key={"experiment_id": f"CHAOSLOCK#{scenario_type}", "created_at": "ACTIVE"})
```

**Key insight**: TTL on lock item is a safety net — if stop fails to release the lock, it auto-expires.

## R4: Auto-Restore Lambda Target

**Decision**: Reuse the Dashboard Lambda as the auto-restore target, with raw event handling BEFORE Powertools routing.

**Rationale**: The Dashboard Lambda already has all the IAM permissions needed to restore chaos. Creating a dedicated restore Lambda would duplicate 100% of this code.

**Critical architecture note**: EventBridge Scheduler invokes Lambda directly via `lambda:InvokeFunction` — it does NOT send an HTTP-formatted event. The Powertools `LambdaFunctionUrlResolver` expects `rawPath` and `requestContext.http.method`, which Scheduler does NOT provide. Therefore, the auto-restore event MUST be handled in `lambda_handler()` BEFORE Powertools routing.

**Event format for auto-restore** (raw Lambda invocation, NOT HTTP):
```json
{
    "action": "chaos-auto-restore",
    "experiment_id": "abc-123"
}
```

**Implementation in lambda_handler()**:
```python
def lambda_handler(event, context):
    # Handle EventBridge Scheduler auto-restore BEFORE Powertools routing
    if event.get("action") == "chaos-auto-restore":
        experiment_id = event.get("experiment_id")
        return _handle_auto_restore(experiment_id)

    # Normal Powertools HTTP routing
    return app.resolve(event, context)
```

**Alternative considered**: Dedicated restore Lambda — rejected because it would need identical IAM permissions and duplicate the entire chaos.py restore logic.
**Alternative considered**: Wrapping event in Function URL format — rejected because it's fragile and Powertools might validate event structure.

## R5: EventBridge Scheduler IAM Role

**Decision**: Create a new IAM role `{env}-chaos-scheduler-role` that allows EventBridge Scheduler to invoke the Dashboard Lambda.

**Rationale**: EventBridge Scheduler needs its own execution role to invoke Lambda targets. This is a standard AWS pattern.

**Terraform resource needed**:
```hcl
resource "aws_iam_role" "chaos_scheduler" {
    assume_role_policy = jsonencode({
        Statement = [{
            Action = "sts:AssumeRole"
            Effect = "Allow"
            Principal = { Service = "scheduler.amazonaws.com" }
        }]
    })
}

resource "aws_iam_role_policy" "chaos_scheduler_invoke" {
    role = aws_iam_role.chaos_scheduler.id
    policy = jsonencode({
        Statement = [{
            Action = "lambda:InvokeFunction"
            Effect = "Allow"
            Resource = module.dashboard_lambda.function_arn
        }]
    })
}
```
