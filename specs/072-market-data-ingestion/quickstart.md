# Quickstart: Market Data Ingestion

**Branch**: `072-market-data-ingestion` | **Date**: 2025-12-09 | **Phase**: 1

## Prerequisites

- Python 3.13+
- AWS credentials configured (LocalStack for local dev)
- API keys for Tiingo and Finnhub (free tier)

## Local Development Setup

### 1. Install Dependencies

```bash
cd /home/traylorre/projects/sentiment-analyzer-gsk
make install
```

### 2. Configure API Keys

Create/update `.env.local`:

```bash
# Data source API keys
TIINGO_API_KEY=your_tiingo_key_here
FINNHUB_API_KEY=your_finnhub_key_here

# AWS/LocalStack configuration
CLOUD_REGION=us-east-1
DATABASE_TABLE=sentiment-analyzer-local

# Cache TTL (seconds)
API_CACHE_TTL_NEWS_SECONDS=1800
API_CACHE_TTL_OHLC_SECONDS=3600
```

### 3. Start LocalStack

```bash
make localstack-up
make tf-init-local
make tf-apply-local
```

### 4. Verify Setup

```bash
# Check adapters work
python -c "
from src.lambdas.shared.adapters.tiingo import TiingoAdapter
from src.lambdas.shared.adapters.finnhub import FinnhubAdapter
import os

tiingo = TiingoAdapter(os.environ['TIINGO_API_KEY'])
finnhub = FinnhubAdapter(os.environ['FINNHUB_API_KEY'])

# Test news fetch
news = tiingo.get_news(['AAPL'], limit=5)
print(f'Tiingo: {len(news)} articles')

news = finnhub.get_news(['AAPL'], limit=5)
print(f'Finnhub: {len(news)} articles')
"
```

## Running Tests

### Unit Tests (Mocked APIs)

```bash
make test-unit
# Or specifically:
pytest tests/unit/ingestion/ -v
```

### Integration Tests (LocalStack)

```bash
make test-integration
# Or specifically:
pytest tests/integration/ingestion/ -v --tb=short
```

## Manual Testing

### Invoke Collection Locally

```bash
# Simulate scheduled collection
python -c "
import json
from src.lambdas.ingestion.handler import handler

event = {
    'source': 'schedule.aws.events',
    'detail-type': 'Scheduled Event',
    'time': '2025-12-09T14:30:00Z'
}

result = handler(event, None)
print(json.dumps(result, indent=2))
"
```

### Check Deduplication

```bash
# Run collection twice - second run should show fewer new items
python -c "
from src.lambdas.ingestion.handler import handler

result1 = handler({'source': 'test'}, None)
print(f'Run 1: {result1[\"new_items\"]} new items')

result2 = handler({'source': 'test'}, None)
print(f'Run 2: {result2[\"new_items\"]} new items (should be fewer)')
"
```

## Key Files

| File | Purpose |
|------|---------|
| `src/lambdas/shared/adapters/tiingo.py` | Primary data source adapter |
| `src/lambdas/shared/adapters/finnhub.py` | Secondary data source adapter |
| `src/lambdas/shared/adapters/base.py` | Base adapter class and models |
| `src/lambdas/shared/dynamodb.py` | DynamoDB helpers with deduplication |
| `src/lambdas/shared/circuit_breaker.py` | Failover pattern |
| `src/lambdas/ingestion/handler.py` | Main Lambda handler (to be created) |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TIINGO_API_KEY` | Yes | - | Tiingo API token |
| `FINNHUB_API_KEY` | Yes | - | Finnhub API token |
| `CLOUD_REGION` | Yes | - | AWS region |
| `DATABASE_TABLE` | Yes | - | DynamoDB table name |
| `SNS_TOPIC_ARN` | No | - | SNS topic for notifications |
| `API_CACHE_TTL_NEWS_SECONDS` | No | 1800 | Cache TTL for news |
| `FAILOVER_TIMEOUT_SECONDS` | No | 10 | Timeout before failover |
| `ALERT_FAILURE_THRESHOLD` | No | 3 | Consecutive failures for alert |

## Troubleshooting

### "Tiingo rate limit exceeded"

```bash
# Clear cache and wait
python -c "
from src.lambdas.shared.adapters.tiingo import clear_cache
clear_cache()
print('Cache cleared - wait 60s before retrying')
"
```

### "No items collected"

1. Check API keys are valid
2. Verify market hours (9:30 AM - 4:00 PM ET)
3. Check network connectivity to external APIs

### "DynamoDB conditional check failed"

This is expected for duplicates. Check logs for actual error vs deduplication:

```bash
grep "ConditionalCheckFailedException" logs/ingestion.log | wc -l
# High count = working deduplication
```

## Next Steps

After local testing passes:

1. Run `/speckit.tasks` to generate implementation tasks
2. Create feature branch `072-market-data-ingestion`
3. Implement tasks in order
4. PR → CI → Deploy to dev
