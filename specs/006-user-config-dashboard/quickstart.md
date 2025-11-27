# Quickstart: Financial News Sentiment & Asset Volatility Dashboard

**Feature**: 006-user-config-dashboard | **Date**: 2025-11-26

## Prerequisites

- Python 3.13+
- Node.js 20+ (for frontend)
- AWS CLI configured with dev credentials
- Terraform 1.5+
- Docker (for LocalStack testing)

## Quick Start (5 minutes)

### 1. Clone and Setup

```bash
cd /home/traylorre/projects/sentiment-analyzer-gsk

# Install Python dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install frontend dependencies
cd src/dashboard
npm install
cd ../..
```

### 2. Environment Configuration

Create `.env` file in project root:

```bash
# AWS Configuration
AWS_REGION=us-east-1
ENVIRONMENT=dev

# API Keys (get from Secrets Manager in dev)
TIINGO_API_KEY=your_tiingo_key
FINNHUB_API_KEY=your_finnhub_key
SENDGRID_API_KEY=your_sendgrid_key

# DynamoDB Tables
DYNAMODB_USERS_TABLE=dev-sentiment-users
DYNAMODB_ITEMS_TABLE=dev-sentiment-items
DYNAMODB_NOTIFICATIONS_TABLE=dev-sentiment-notifications

# Cognito (get from Terraform output)
COGNITO_USER_POOL_ID=us-east-1_xxxxx
COGNITO_CLIENT_ID=xxxxx
COGNITO_DOMAIN=sentiment-dev.auth.us-east-1.amazoncognito.com
```

### 3. Run Unit Tests

```bash
# Run all unit tests (mocked AWS)
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/lambdas/ingestion/test_tiingo_adapter.py -v

# Run with coverage
pytest tests/unit/ --cov=src --cov-report=html
```

### 4. Run Integration Tests (requires dev AWS)

```bash
# Ensure dev environment is deployed
cd infrastructure/terraform
terraform workspace select dev
terraform plan  # Verify no changes needed

# Run integration tests against real dev resources
cd ../..
ENVIRONMENT=dev pytest tests/integration/ -v -m "not preprod"
```

### 5. Local Lambda Development

```bash
# Start local Lambda with SAM
cd infrastructure/sam
sam local start-api --env-vars env.json

# In another terminal, test endpoints
curl http://localhost:3000/api/v2/health
```

### 6. Frontend Development

```bash
cd src/dashboard

# Start development server
npm run dev

# Open browser to http://localhost:3000
```

---

## API Key Setup

### Tiingo API Key

1. Sign up at https://www.tiingo.com/
2. Navigate to API → Token
3. Copy token to Secrets Manager: `aws secretsmanager put-secret-value --secret-id dev/sentiment-analyzer/tiingo-api-key --secret-string '{"api_key":"YOUR_KEY"}'`

### Finnhub API Key

1. Sign up at https://finnhub.io/
2. Navigate to Dashboard → API Key
3. Copy token to Secrets Manager: `aws secretsmanager put-secret-value --secret-id dev/sentiment-analyzer/finnhub-api-key --secret-string '{"api_key":"YOUR_KEY"}'`

### SendGrid API Key

1. Sign up at https://sendgrid.com/
2. Navigate to Settings → API Keys → Create API Key
3. Select "Restricted Access" with Mail Send permissions
4. Copy to Secrets Manager: `aws secretsmanager put-secret-value --secret-id dev/sentiment-analyzer/sendgrid-api-key --secret-string '{"api_key":"YOUR_KEY"}'`

---

## Local Development with Mocks

### Using moto for AWS Mocking

```python
# tests/conftest.py already configures moto
# Unit tests automatically use mocked AWS services

@pytest.fixture
def dynamodb_table():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-sentiment-items",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table
```

### Mocking Financial APIs

```python
# tests/fixtures/tiingo_responses.py
TIINGO_NEWS_RESPONSE = [
    {
        "id": 123456,
        "title": "Apple Reports Strong Q4 Earnings",
        "description": "Apple Inc. reported...",
        "publishedDate": "2025-11-25T14:30:00Z",
        "tickers": ["AAPL"],
        "tags": ["earnings", "technology"],
        "source": "bloomberg"
    }
]

# In tests
@responses.activate
def test_tiingo_adapter():
    responses.add(
        responses.GET,
        "https://api.tiingo.com/tiingo/news",
        json=TIINGO_NEWS_RESPONSE,
        status=200
    )
    adapter = TiingoAdapter("fake_key")
    news = adapter.get_news(["AAPL"], "2025-11-01")
    assert len(news) == 1
```

---

## Terraform Development

### Initialize and Plan

```bash
cd infrastructure/terraform

# Initialize with S3 backend
terraform init

# Select workspace
terraform workspace select dev  # or: terraform workspace new dev

# Plan changes
terraform plan -var="environment=dev"

# Apply changes
terraform apply -var="environment=dev"
```

### Common Terraform Commands

```bash
# List resources
terraform state list

# Show specific resource
terraform state show module.lambda.aws_lambda_function.ingestion

# Import existing resource
terraform import -var="environment=dev" \
  module.secrets.aws_secretsmanager_secret.tiingo \
  dev/sentiment-analyzer/tiingo-api-key

# Destroy (CAUTION!)
terraform destroy -var="environment=dev"
```

---

## Debugging

### Lambda Logs

```bash
# Tail ingestion Lambda logs
aws logs tail /aws/lambda/dev-sentiment-ingestion --follow

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-sentiment-dashboard \
  --filter-pattern "ERROR"
```

### X-Ray Traces

```bash
# Get recent traces
aws xray get-trace-summaries \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s)

# Get specific trace
aws xray batch-get-traces --trace-ids "1-xxxxx-xxxxx"
```

### DynamoDB Queries

```bash
# Query sentiment items for a ticker
aws dynamodb query \
  --table-name dev-sentiment-items \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk": {"S": "TICKER#AAPL"}}'

# Scan users table
aws dynamodb scan \
  --table-name dev-sentiment-users \
  --limit 10
```

---

## Common Tasks

### Adding a New Ticker Adapter

1. Create adapter file: `src/lambdas/ingestion/adapters/new_source.py`
2. Implement `BaseAdapter` interface
3. Add unit tests in `tests/unit/lambdas/ingestion/test_new_source.py`
4. Register adapter in `src/lambdas/ingestion/handler.py`
5. Add integration test

### Creating a New API Endpoint

1. Add route handler in `src/lambdas/dashboard/api_v2.py`
2. Add Pydantic request/response models
3. Add unit tests
4. Update `contracts/dashboard-api.md` with new endpoint
5. Run integration tests

### Modifying DynamoDB Schema

1. Update models in `src/lambdas/shared/models/`
2. Update Terraform if new table/GSI needed
3. Run migrations script if needed
4. Update `data-model.md`
5. Run all tests

---

## Troubleshooting

### "Module not found" errors

```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### "Credentials not found" errors

```bash
# Check AWS configuration
aws sts get-caller-identity

# Ensure correct profile
export AWS_PROFILE=dev
```

### "Table not found" errors

```bash
# Verify tables exist
aws dynamodb list-tables

# Check environment variable
echo $DYNAMODB_ITEMS_TABLE
```

### Frontend build errors

```bash
# Clear cache and reinstall
cd src/dashboard
rm -rf node_modules .next
npm install
npm run dev
```

---

## Security Middleware

### Rate Limiting

```python
from src.lambdas.shared.middleware.rate_limit import (
    check_rate_limit,
    get_client_ip,
    get_rate_limit_headers,
)

def handler(event, context):
    client_ip = get_client_ip(event)
    result = check_rate_limit(table, client_ip, action="config_create")

    if not result.allowed:
        return {
            "statusCode": 429,
            "headers": get_rate_limit_headers(result),
            "body": json.dumps({"error": "Rate limit exceeded"})
        }
    # ... process request
```

### hCaptcha Verification

```python
from src.lambdas.shared.middleware.hcaptcha import (
    verify_captcha,
    should_require_captcha,
)

# Check if captcha should be required (3+ requests/hour)
if should_require_captcha(table, client_ip, action="config_create"):
    captcha_token = event.get("headers", {}).get("x-captcha-token")
    if not captcha_token:
        return {"statusCode": 400, "body": "Captcha required"}

    result = verify_captcha(captcha_token, client_ip)
    if not result.success:
        return {"statusCode": 403, "body": "Captcha verification failed"}
```

### Security Headers

```python
from src.lambdas.shared.middleware.security_headers import (
    add_security_headers,
    get_preflight_response,
)

def handler(event, context):
    # Handle CORS preflight
    if event.get("httpMethod") == "OPTIONS":
        return get_preflight_response(origin=event["headers"].get("origin"))

    # Process request...
    response = {"statusCode": 200, "body": json.dumps(result)}

    # Add security headers before returning
    return add_security_headers(response, origin=event["headers"].get("origin"))
```

---

## Synthetic Test Data

The project includes deterministic test data generators for E2E testing:

```python
from tests.fixtures.synthetic import (
    TickerGenerator,
    SentimentGenerator,
    NewsGenerator,
    TestOracle,
)

# Generate deterministic OHLC price data
ticker_gen = TickerGenerator(seed=42)
candles = ticker_gen.generate_ohlc("AAPL", days=30, volatility_periods=[(10, 20)])

# Generate sentiment scores with bullish/bearish periods
sentiment_gen = SentimentGenerator(seed=42)
scores = sentiment_gen.generate_scores("AAPL", days=30, bullish_periods=[(0, 10)])

# Generate news articles by sentiment
news_gen = NewsGenerator(seed=42)
articles = news_gen.generate_articles("AAPL", count=10, sentiment="positive")

# Compute expected outcomes (test oracle)
oracle = TestOracle()
expected_atr = oracle.calculate_expected_atr(candles)
expected_sentiment = oracle.calculate_expected_sentiment(scores)
```

### E2E Test Context

```python
from tests.e2e.conftest import E2ETestContext

def test_complete_flow(e2e_context: E2ETestContext):
    # Mock APIs are pre-configured with synthetic data
    with e2e_context.tiingo_mock, e2e_context.finnhub_mock:
        # Create config, fetch data, verify results
        response = client.get(f"/api/v2/configurations/{config_id}/sentiment")
        assert response.status_code == 200

        # Verify against test oracle
        expected = e2e_context.oracle.calculate_expected_sentiment(config.tickers)
        assert response.json()["score"] == pytest.approx(expected, rel=0.01)
```

---

## CI/CD Integration

### GitHub Actions Workflow

The `.github/workflows/deploy.yml` workflow:
1. Runs unit tests on every PR
2. Runs integration tests on merge to main
3. Deploys to preprod on main merge
4. Deploys to prod on release tag

### Running CI Locally

```bash
# Install act (GitHub Actions local runner)
brew install act  # or download from https://github.com/nektos/act

# Run unit tests workflow
act -j unit-tests

# Run full workflow (requires AWS secrets)
act -j deploy --secret-file .secrets
```
