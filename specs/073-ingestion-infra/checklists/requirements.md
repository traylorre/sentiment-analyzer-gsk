# Requirements Checklist: Infrastructure Provisioning for Market Data Ingestion

**Purpose**: Verify all functional requirements and success criteria from spec.md
**Created**: 2025-12-09
**Feature**: [spec.md](../spec.md)

## Functional Requirements

### Scheduling (FR-001, FR-002)

- [ ] FR001 EventBridge rule triggers every 5 minutes during market hours (9:30 AM - 4:00 PM ET, Mon-Fri)
- [ ] FR002 EventBridge rule disabled outside market hours (cost optimization)

### Alerting (FR-003, FR-004, FR-007)

- [ ] FR003 SNS topic delivers failure alerts when 3 consecutive failures occur within 15 minutes
- [ ] FR004 SNS topic delivers high-latency alerts when collection exceeds 30 seconds
- [ ] FR007 Subscription management for operations team alerts (email protocol)

### Monitoring (FR-005, FR-008)

- [ ] FR005 CloudWatch dashboard displays: success rate, failure count, latency, failover events, items collected
- [ ] FR008 Budget alerts configured at $10, $25, $50 thresholds

### Notification (FR-006)

- [ ] FR006 SNS topic publishes downstream notifications within 30 seconds of data storage

### Cost Controls (FR-009, FR-010)

- [ ] FR009 All storage uses on-demand capacity (no provisioned DynamoDB)
- [ ] FR010 No NAT Gateway usage (VPC endpoints if network access needed)

## Success Criteria

- [ ] SC001 Ingestion runs every 5 minutes during market hours with 99.5% schedule reliability
- [ ] SC002 Operations team receives failure alerts within 5 minutes of 3rd consecutive failure
- [ ] SC003 Dashboard displays all metrics, updates within 5 minutes of collection events
- [ ] SC004 Downstream notifications published within 30 seconds of data storage
- [ ] SC005 All infrastructure passes validation checks (security, cost, formatting)
- [ ] SC006 Monthly dev environment infrastructure cost under $10

## User Stories Coverage

### US1 - Scheduled Data Collection (P1)

- [ ] US1-1 Automatic collection during market hours
- [ ] US1-2 No collection outside market hours
- [ ] US1-3 Data appears in storage within 5 minutes of trigger

### US2 - Operational Alerting (P1)

- [ ] US2-1 Alert on 3 consecutive failures within 15 minutes
- [ ] US2-2 No duplicate alerts for same incident
- [ ] US2-3 High-latency alert when collection exceeds 30 seconds

### US3 - Monitoring Dashboard (P2)

- [ ] US3-1 Dashboard shows success rate, failure count, latency metrics
- [ ] US3-2 Metrics update within 5 minutes
- [ ] US3-3 24-hour historical trend visibility

### US4 - Downstream Notification (P2)

- [ ] US4-1 Notification published within 30 seconds of storage
- [ ] US4-2 Message includes item count, source, timestamp
- [ ] US4-3 No notification on storage failure

## Infrastructure Components

- [ ] INF001 EventBridge schedule rule (market hours cron)
- [ ] INF002 SNS topic for operational alerts
- [ ] INF003 SNS topic for downstream notifications
- [ ] INF004 CloudWatch dashboard with 5 widget panels
- [ ] INF005 Budget alerts with 3 thresholds
- [ ] INF006 IAM roles with least-privilege permissions

## Validation Gates

- [ ] VAL001 `/iam-validate` passes (no overly permissive policies)
- [ ] VAL002 `/cost-validate` passes (no expensive patterns flagged)
- [ ] VAL003 `/security-validate` passes (no hardcoded secrets)
- [ ] VAL004 `terraform plan` shows expected resource count
- [ ] VAL005 `make validate` passes on all checks

## Notes

- Check items off as completed: `[x]`
- Items are numbered by category for traceability
- FR = Functional Requirement, SC = Success Criteria, US = User Story
- INF = Infrastructure Component, VAL = Validation Gate
