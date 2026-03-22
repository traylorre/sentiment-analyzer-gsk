# Chaos GameDay Pre-Flight Checklist

**Purpose**: Verify all pre-conditions before executing a chaos plan. Every item must be checked. Any No-Go condition aborts the GameDay.

**When to use**: Before every GameDay. Do not skip items even if "you just checked yesterday."

---

## Checklist

### 1. Environment Health

- [ ] Run environment status check:
  ```bash
  scripts/chaos/status.sh preprod
  ```
- [ ] DynamoDB: **healthy** (status.sh confirms `describe-table` succeeds)
- [ ] SSM: **healthy** (status.sh confirms parameter store accessible)
- [ ] CloudWatch: **healthy** (status.sh confirms `describe-alarms` succeeds)
- [ ] Lambda: **healthy** (status.sh confirms `get-function` succeeds for ingestion Lambda)

### 2. Alarm States

- [ ] All critical alarms in **OK** state:
  ```bash
  aws cloudwatch describe-alarms \
    --alarm-name-prefix "preprod-" \
    --state-value ALARM \
    --query "MetricAlarms[].AlarmName" \
    --output text
  ```
  Expected: empty output (no alarms in ALARM state)

- [ ] Composite alarm in OK state:
  ```bash
  aws cloudwatch describe-alarms \
    --alarm-names "preprod-critical-composite" \
    --query "CompositeAlarms[].StateValue" \
    --output text
  ```
  Expected: `OK`

### 3. Dashboard Accessibility

- [ ] Dashboard Function URL is reachable:
  ```bash
  curl -s -o /dev/null -w "%{http_code}" https://<DASHBOARD_FUNCTION_URL>/health
  ```
  Expected: `200`

- [ ] Chaos endpoint responds:
  ```bash
  curl -s -o /dev/null -w "%{http_code}" https://<DASHBOARD_FUNCTION_URL>/chaos
  ```
  Expected: `200`

### 4. Chaos Gate State

- [ ] Kill switch SSM parameter exists:
  ```bash
  aws ssm get-parameter \
    --name "/chaos/preprod/kill-switch" \
    --query "Parameter.Value" \
    --output text
  ```
  Expected: `disarmed` (will be armed in execution step)

- [ ] No active chaos experiments:
  ```bash
  # Via dashboard API
  curl -s https://<DASHBOARD_FUNCTION_URL>/api/chaos/experiments?status=running | python3 -m json.tool
  ```
  Expected: empty list

### 5. Recent Ingestion Baseline

- [ ] At least one successful ingestion cycle in the last 30 minutes:
  ```bash
  aws cloudwatch get-metric-statistics \
    --namespace SentimentAnalyzer \
    --metric-name ArticlesFetched \
    --start-time "$(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
    --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
    --period 300 \
    --statistics Sum \
    --query "Datapoints[].Sum"
  ```
  Expected: at least one value > 0

### 6. Team Notification

- [ ] Notify team in Slack channel: "Starting Chaos GameDay against preprod. ETA: 60 minutes. Plan: [plan name]"
- [ ] Buddy operator confirmed and available for the full duration
- [ ] Buddy operator has AWS console access and can reach the andon cord:
  ```bash
  scripts/chaos/andon-cord.sh preprod
  ```

### 7. CI/CD Pause

- [ ] No pending pull requests with auto-merge enabled for preprod deploy:
  ```bash
  gh pr list --state open --label "auto-merge" --json number,title
  ```
- [ ] No active Terraform applies targeting preprod
- [ ] No scheduled deployments in the next 90 minutes

### 8. Rollback Readiness

- [ ] Restore script is accessible and executable:
  ```bash
  ls -la scripts/chaos/restore.sh
  ```
- [ ] Andon cord script is accessible:
  ```bash
  ls -la scripts/chaos/andon-cord.sh
  ```
- [ ] Operator knows the emergency phone escalation path

---

## No-Go Criteria

**If ANY of these conditions are true, ABORT the GameDay and investigate first.**

| # | Condition | Why |
|---|-----------|-----|
| NG-1 | Any dependency reported as "degraded" by `status.sh` | Cannot distinguish chaos-induced failures from pre-existing ones. Report verdict will be `COMPROMISED`. |
| NG-2 | Any CloudWatch alarm in ALARM state | Pre-existing alarm masks chaos-induced alarms. |
| NG-3 | Dashboard Function URL unreachable | Cannot create/monitor/stop experiments via API. Fallback (`inject.sh`) is available but reduces observability. |
| NG-4 | Kill switch is "triggered" | Previous chaos experiment did not clean up. Run `scripts/chaos/andon-cord.sh preprod` first. |
| NG-5 | Active chaos experiment already running | Only one experiment at a time. Stop the existing experiment first. |
| NG-6 | No buddy operator available | Safety requirement. Never run chaos alone. |
| NG-7 | Terraform apply in progress or scheduled | Deploy could overwrite chaos-injected configuration, causing unpredictable state. |
| NG-8 | No recent successful ingestion cycle | Cannot verify recovery if there is no baseline of successful operation. |

---

## Sign-Off

| Role | Name | Time | Checklist Complete |
|------|------|------|--------------------|
| Operator | | | [ ] All items checked, no No-Go conditions |
| Buddy | | | [ ] Confirmed available, knows andon cord location |
