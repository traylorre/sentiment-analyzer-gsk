# Fix: Validation & Smoke Test

**Parent:** [HL-fastapi-purge-checklist.md](./HL-fastapi-purge-checklist.md)
**Priority:** P9 (Final step)
**Status:** [ ] TODO
**Depends On:** All previous tasks (P0-P8)

---

## Objective

End-to-end verification that the purge is complete, correct, and produces identical behavior.

---

## Pre-Deployment Validation

### 1. No Remaining References

```bash
# Zero results expected for each
grep -rn "fastapi" src/ tests/ --include="*.py"
grep -rn "mangum" src/ tests/ --include="*.py"
grep -rn "starlette" src/ tests/ --include="*.py"
grep -rn "uvicorn" src/ tests/ --include="*.py"
grep -rn "TestClient" tests/ --include="*.py"
```

### 2. Clean Install

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
# No errors
```

### 3. Import Check

```bash
python -c "from src.lambdas.dashboard.ohlc import lambda_handler; print('Handler: OK')"
# Should succeed

python -c "import fastapi" 2>&1 | grep -q "ModuleNotFoundError" && echo "FastAPI: REMOVED" || echo "FastAPI: STILL PRESENT"
# Should say REMOVED
```

### 4. Unit Tests

```bash
pytest tests/unit/ -v --tb=short
# All pass, same count as before
```

### 5. Terraform Plan

```bash
terraform plan
# Only change should be handler path (no resource recreation)
```

---

## Post-Deployment Smoke Test

### 6. API Endpoint Checks

```bash
# Replace with actual API Gateway URL
API_URL="https://xxx.execute-api.us-east-1.amazonaws.com/prod"

# Health check
curl -s "$API_URL/health" | jq .

# OHLC endpoint
curl -s "$API_URL/api/v2/tickers/AAPL/ohlc?range=1M&resolution=D" | jq .

# Verify CORS headers
curl -sI "$API_URL/api/v2/tickers/AAPL/ohlc" | grep -i "access-control"

# Verify cache header
curl -s -D- "$API_URL/api/v2/tickers/AAPL/ohlc?range=1M" -o /dev/null | grep "X-Cache-Source"
```

### 7. Error Handling

```bash
# Missing parameter
curl -s "$API_URL/api/v2/tickers//ohlc" | jq .
# Should return 400 or 404

# Invalid range
curl -s "$API_URL/api/v2/tickers/AAPL/ohlc?range=INVALID" | jq .
# Should return 400
```

### 8. Playwright E2E

```bash
npx playwright test
# All existing tests pass without modification
```

---

## Performance Comparison

Record before/after metrics:

| Metric | Before (FastAPI) | After (Native) | Delta |
|--------|------------------|-----------------|-------|
| Cold start latency | ___ms | ___ms | ___ms |
| Warm invocation | ___ms | ___ms | ___ms |
| Memory used | ___MB | ___MB | ___MB |
| Package size | ___MB | ___MB | ___MB |

```bash
# Get Lambda metrics from CloudWatch
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=prod-sentiment-dashboard \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

---

## Rollback Plan

If native handler fails in production:

1. Revert Terraform handler to `main.handler`
2. Restore FastAPI packages to requirements
3. Redeploy
4. Investigate failure using CloudWatch logs

**Time to rollback:** ~5 minutes (Terraform apply + Lambda deploy)

---

## Completion Checklist

- [ ] All grep checks return zero results
- [ ] Clean pip install succeeds
- [ ] All unit tests pass
- [ ] Terraform plan shows only handler change
- [ ] Post-deploy API endpoints return correct data
- [ ] CORS headers present
- [ ] Error handling works
- [ ] Playwright E2E passes
- [ ] Performance metrics recorded
- [ ] Rollback plan documented and tested

---

## Related

- [HL-fastapi-purge-checklist.md](./HL-fastapi-purge-checklist.md) - Update status to COMPLETE
- All task files - Mark as DONE
