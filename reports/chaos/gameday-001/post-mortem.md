# Gameday 001 Post-Mortem: Ingestion Resilience

**Date**: TBD
**Participants**: TBD (operator + buddy)
**Environment**: preprod
**Duration**: ~60 minutes (ingestion-resilience plan)
**Plan**: ingestion-resilience (2 scenarios, 6 assertions)

## Pre-Flight Checklist

| Section | Status | Notes |
|---------|--------|-------|
| Environment health | | |
| Alarm states | | |
| Dashboard accessible | | |
| Chaos gate state | | |
| Ingestion baseline | | |
| Team notification | | |
| CI/CD paused | | |
| Rollback readiness | | |

## Scenario Results

### Scenario 1: Ingestion Failure

| Metric | Expected | Actual |
|--------|----------|--------|
| ArticlesFetched drops to 0 | Within 2 min | |
| Error alarm transitions | ALARM within 2 min | |
| Recovery (ArticlesFetched > 0) | Within 10 min | |
| Verdict | CLEAN | |
| Recovery time | | |

### Scenario 2: DynamoDB Throttle

| Metric | Expected | Actual |
|--------|----------|--------|
| Write operations fail | AccessDenied | |
| Lambda error rates increase | Within 2 min | |
| Recovery (writes succeed) | Within 5 min | |
| Verdict | CLEAN | |
| Recovery time | | |

## Safety Mechanism Validation

| Mechanism | Tested | Status | Notes |
|-----------|--------|--------|-------|
| Kill switch blocking | | | |
| Auto-restore Lambda | | | |
| Andon cord (stretch) | | | |

## Assertions (from ingestion-resilience.yaml)

| # | Assertion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |
| 6 | | | |

## Unexpected Findings

1. TBD

## Action Items

| # | Action | Owner | Due |
|---|--------|-------|-----|
| 1 | | | |

## Summary

TBD — fill after gameday execution.
