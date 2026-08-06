# Chaos Testing

> **CANON**: verified against code.

Current state: not operational.

Fault injection for the sentiment analyzer. Faults are injected by degrading
infrastructure externally through AWS API calls; the application Lambdas are unaware.
Two entry points: the chaos endpoints on the dashboard Lambda, and the scripts under
`scripts/chaos/`. Report generation and baseline diffing are not yet built; this doc
does not cover them.

## What exists

| Piece | Where |
|---|---|
| Injection scripts | `scripts/chaos/inject.sh`, `restore.sh`, `status.sh`, `andon-cord.sh` |
| Chaos plans | `chaos-plans/ingestion-resilience.yaml`, `chaos-plans/cold-start-resilience.yaml` |
| API endpoints | `src/lambdas/dashboard/chaos.py`, routed in `handler.py` (`/chaos/experiments`) |
| Auto-restore Lambda | `src/lambdas/chaos_restore/handler.py` |
| Terraform | `infrastructure/terraform/modules/chaos/` |
| Preflight checklist | `docs/chaos-testing/preflight-checklist.md` |

Constraints that shape usage:

- The dashboard chaos API serves only `local`, `dev`, and `test`. Preprod, prod, and
  unknown environments get 404 (fail-closed env gate in `handler.py`). The plans target
  preprod, so a preprod gameday runs through the scripts, not the API.
- Chaos API calls need a JWT-authenticated user with the operator role.
- The FIS experiment templates in the chaos terraform module are disabled; nothing runs
  through AWS FIS.
- Production chaos is not supported by any path.

## Scenarios

`scripts/chaos/inject.sh <scenario> <environment> [--target <service>] [--duration <sec>] [--dry-run]`
(duration defaults to 300s and auto-restores; dry-run prints the AWS commands without
executing):

| Scenario | Injection | What to observe |
|---|---|---|
| `ingestion-failure` | Reserved concurrency 0 on the ingestion Lambda | Throttles rise, Invocations and `ArticlesFetched` drop to 0 |
| `dynamodb-throttle` | Deny-write IAM policy attached to ingestion and analysis execution roles | `AccessDeniedException` in Lambda logs, error counts rise |
| `cold-start` | Target Lambda memory set to 128MB | `Duration` metric rises |
| `api-timeout` | Target Lambda timeout set to 1s | All invocations fail |
| `trigger-failure` | EventBridge ingestion schedule rule disabled | Invocations stop with no errors |

IAM policy propagation for `dynamodb-throttle` can take up to 60 seconds, so effects
may lag the injection.

## Chaos plans

A plan is a YAML file in `chaos-plans/` naming the scenarios, durations, blast radius,
assertions, and required gate state. Two exist:

- `ingestion-resilience.yaml`: `ingestion_failure` then `dynamodb_throttle`. Run first;
  it establishes the baseline.
- `cold-start-resilience.yaml`: `lambda_cold_start` then `api_timeout`.

Both declare `environment: preprod` and require the gate armed.

## Safety mechanisms

- **Kill switch**: SSM parameter `/chaos/<env>/kill-switch`, values `disarmed`
  (default, dry-run only), `armed`, `triggered`. A missing parameter is treated as
  first-time setup and injection proceeds; an unreachable SSM blocks injection.
- **Snapshots**: pre-chaos Lambda configuration is written to SSM under
  `/chaos/<env>/snapshot/` before injection, and restoration reads from there.
- **Andon cord**: `scripts/chaos/andon-cord.sh <env>` sets the switch to `triggered`,
  restores every snapshot, and detaches deny policies.
- **Auto-restore Lambda**: code-complete but not deployed. The terraform module
  invocation is still a TODO in `infrastructure/terraform/main.tf`, and its intended
  trigger, the `preprod-critical-composite` alarm, does not exist in preprod because
  the cloudwatch-alarms module is gated off there. Until both land, deployed safety is
  the kill switch, the snapshots, and the andon cord.
- **Buddy operator**: every gameday has a second operator watching alarms, ready to
  pull the andon cord.

## Running a gameday

A gameday executes one plan against preprod with an operator and a buddy. Budget about
an hour.

1. **Preflight.** Complete every item in
   [`docs/chaos-testing/preflight-checklist.md`](chaos-testing/preflight-checklist.md).
   `scripts/chaos/status.sh preprod` gives a quick health read. Any no-go condition
   aborts the gameday.
2. **Arm the gate.**

   ```bash
   aws ssm put-parameter --name "/chaos/preprod/kill-switch" \
     --value "armed" --type String --overwrite
   ```

3. **Run each scenario in plan order.** For each one: inject with
   `scripts/chaos/inject.sh <scenario> preprod --duration 120`, observe the scenario's
   metrics for the injection window, restore with `scripts/chaos/restore.sh preprod`,
   then watch recovery for about 5 minutes. Ingestion recovery shows on the next
   EventBridge-triggered invocation (5 minute schedule); alarms should transition from
   ALARM back to OK. Wait at least 2 minutes after recovery before the next scenario so
   effects do not overlap.
4. **Disarm the gate.** Same `put-parameter` with value `disarmed`.
5. **Post-mortem.** For each scenario record the verdict, actual versus expected
   recovery time, whether alarms fired, whether manual intervention was needed, and a
   pass/fail per plan assertion. Write up findings and follow-ups, and notify the team.

The scripts log experiments to the chaos DynamoDB table, so the audit trail exists even
when the API path is not used.

## Emergency procedures

Anything goes wrong, pull the andon cord:

```bash
scripts/chaos/andon-cord.sh preprod
```

If the andon cord itself fails, restore by hand:

```bash
aws lambda delete-function-concurrency --function-name preprod-sentiment-ingestion
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws iam detach-role-policy --role-name preprod-ingestion-lambda-role \
  --policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/preprod-chaos-deny-dynamodb-write" || true
aws iam detach-role-policy --role-name preprod-analysis-lambda-role \
  --policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/preprod-chaos-deny-dynamodb-write" || true
aws lambda update-function-configuration --function-name preprod-sentiment-analysis --memory-size 2048
aws lambda update-function-configuration --function-name preprod-sentiment-ingestion --timeout 60
aws events enable-rule --name preprod-sentiment-ingestion-schedule
aws ssm put-parameter --name "/chaos/preprod/kill-switch" \
  --value "disarmed" --type String --overwrite
```

Escalation: buddy pulls the cord; if the cord fails, operator and buddy run the manual
restore above. There is no escalation chain beyond the two of them.
