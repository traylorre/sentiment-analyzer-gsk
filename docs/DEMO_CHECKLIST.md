# Demo Day Checklist

Checklist for presenting the Sentiment Analyzer demo.

---

## 30 Minutes Before Demo

### System Verification

- [ ] Run validation script
  ```bash
  ./infrastructure/scripts/demo-validate.sh dev
  ```

- [ ] Verify all alarms are OK (not firing)
  ```bash
  aws cloudwatch describe-alarms \
    --alarm-name-prefix dev-sentiment \
    --state-value ALARM
  ```

- [ ] Check secrets are accessible
  ```bash
  aws secretsmanager get-secret-value \
    --secret-id dev/sentiment-analyzer/newsapi \
    --query 'SecretString' | jq .
  ```

- [ ] Verify data exists in DynamoDB
  ```bash
  aws dynamodb scan \
    --table-name dev-sentiment-items \
    --select COUNT
  ```

### Dashboard Verification

- [ ] Get dashboard URL
  ```bash
  aws lambda get-function-url-config \
    --function-name dev-sentiment-dashboard \
    --query 'FunctionUrl' --output text
  ```

- [ ] Test dashboard health endpoint
  ```bash
  curl -s "$(aws lambda get-function-url-config \
    --function-name dev-sentiment-dashboard \
    --query 'FunctionUrl' --output text)health"
  ```

- [ ] Open dashboard in browser and verify:
  - [ ] Page loads without errors
  - [ ] Metrics cards display numbers
  - [ ] Pie chart renders
  - [ ] Bar chart renders
  - [ ] Recent items table populated

### Data Refresh (If Needed)

- [ ] Trigger manual ingestion
  ```bash
  aws lambda invoke \
    --function-name dev-sentiment-ingestion \
    --payload '{}' \
    /tmp/demo-response.json
  ```

- [ ] Wait 60 seconds for analysis

- [ ] Verify sentiment distribution
  ```bash
  for s in positive neutral negative; do
    echo -n "$s: "
    aws dynamodb query \
      --table-name dev-sentiment-items \
      --index-name by_sentiment \
      --key-condition-expression "sentiment = :s" \
      --expression-attribute-values "{\":s\": {\"S\": \"$s\"}}" \
      --select COUNT --query Count --output text
  done
  ```

---

## During Demo

### Demo Script

1. **Introduction** (2 min)
   - Show architecture diagram
   - Explain data flow: NewsAPI → Ingestion → SNS → Analysis → Dashboard

2. **Live Dashboard** (5 min)
   - Display dashboard URL in browser
   - Point out:
     - Real-time metrics cards
     - Sentiment distribution (pie chart)
     - Tag distribution (bar chart)
     - Recent items with sentiment badges
   - Show SSE connection (items update automatically)

3. **Trigger Live Update** (3 min)
   - Manually invoke ingestion
   - Watch dashboard update in real-time
   - Explain deduplication (same articles won't appear twice)

4. **Infrastructure** (3 min)
   - Show Terraform structure
   - Explain module reusability
   - Point out CloudWatch alarms

5. **Q&A** (5 min)

### Useful Commands During Demo

```bash
# Trigger ingestion
aws lambda invoke \
  --function-name dev-sentiment-ingestion \
  --payload '{}' response.json && cat response.json

# Watch CloudWatch logs
aws logs tail /aws/lambda/dev-sentiment-ingestion --follow

# Check recent items
aws dynamodb query \
  --table-name dev-sentiment-items \
  --index-name by_status \
  --key-condition-expression "#st = :s" \
  --expression-attribute-names '{"#st": "status"}' \
  --expression-attribute-values '{":s": {"S": "analyzed"}}' \
  --scan-index-forward false \
  --limit 5 \
  --query 'Items[*].[title.S, sentiment.S]' \
  --output table

# Get sentiment counts
for s in positive neutral negative; do
  count=$(aws dynamodb query \
    --table-name dev-sentiment-items \
    --index-name by_sentiment \
    --key-condition-expression "sentiment = :s" \
    --expression-attribute-values "{\":s\": {\"S\": \"$s\"}}" \
    --select COUNT --query Count --output text)
  echo "$s: $count"
done
```

### Troubleshooting During Demo

| Issue | Quick Fix |
|-------|-----------|
| Dashboard not loading | Check Lambda logs: `aws logs tail /aws/lambda/dev-sentiment-dashboard --since 5m` |
| No data showing | Trigger ingestion manually |
| Charts not updating | Refresh browser, check SSE connection |
| API errors | Check API key in Secrets Manager |
| Lambda timeout | Point out this is expected for cold starts |

---

## After Demo

### Collect Feedback

- [ ] Note questions asked
- [ ] Record any issues encountered
- [ ] List suggested improvements

### Cleanup (Optional)

If cleaning up demo data:

```bash
./infrastructure/scripts/demo-teardown.sh dev
```

### Post-Demo Report

Document:
1. Demo date and audience
2. Issues encountered
3. Questions asked
4. Action items for improvements

---

## Emergency Contacts

- **On-Call Engineer**: See ON_CALL_SOP.md
- **AWS Support**: Check AWS Health Dashboard
- **NewsAPI Status**: https://newsapi.org/

---

## Backup Plans

### If NewsAPI Is Down

- Show existing data in DynamoDB
- Explain the system stores historical data
- Demonstrate dashboard with cached data

### If Lambda Cold Start Is Slow

- Pre-warm Lambdas before demo:
  ```bash
  for fn in ingestion analysis dashboard; do
    aws lambda invoke \
      --function-name "dev-sentiment-${fn}" \
      --payload '{"warmup": true}' \
      /dev/null &
  done
  wait
  ```

### If Dashboard Is Unresponsive

- Check CloudWatch logs
- Verify DynamoDB is accessible
- Show API response directly:
  ```bash
  curl -s "$(aws lambda get-function-url-config \
    --function-name dev-sentiment-dashboard \
    --query 'FunctionUrl' --output text)api/metrics" | jq .
  ```

---

*Last updated: 2025-11-18*
