# sentiment-analyzer-gsk Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-11-26

## Active Technologies
- TypeScript 5.x, Node.js 20 LTS (007-sentiment-dashboard-frontend)
- Python 3.13 + pytest, pytest-asyncio, httpx, boto3, moto (for local unit tests only), aws-xray-sdk (008-e2e-validation-suite)
- DynamoDB (preprod - real AWS, no mocks for E2E) (008-e2e-validation-suite)
- Python 3.13 + pytest, pytest-asyncio, httpx, boto3, moto (unit tests only) (009-e2e-test-oracle-validation)
- Python 3.13 (backend), TypeScript 5 (frontend) + FastAPI 0.121.3, httpx 0.28.1, TradingView Lightweight Charts 5.0.9, React 18, Next.js 14.2.21, Zustand 5.0.8, React Query 5.90.11 (011-price-sentiment-overlay)
- DynamoDB (single-table design), in-memory cache for OHLC data (011-price-sentiment-overlay)
- Python 3.13 + pytest, pytest-asyncio, httpx, responses, moto (unit tests only) (012-ohlc-sentiment-e2e-tests)
- N/A (test suite - no storage requirements) (012-ohlc-sentiment-e2e-tests)
- JavaScript ES6+ (vanilla, no framework) + Hammer.js or custom touch event handling (research needed) (013-interview-swipe-gestures)
- N/A (stateless UI feature) (013-interview-swipe-gestures)
- Python 3.13 (backend), TypeScript 5 (frontend) + FastAPI 0.121.3, boto3, pydantic, aws-lambda-powertools (backend); React 18, Next.js 14.2.21, Zustand 5.0.8, React Query 5.90.11 (frontend) (014-session-consistency)
- DynamoDB (single-table design with GSIs for email lookup) (014-session-consistency)
- Python 3.13 + FastAPI, sse-starlette, boto3, aws-xray-sdk, AWS Lambda Web Adapter (016-sse-streaming-lambda)
- DynamoDB (existing tables - read-only access for SSE Lambda) (016-sse-streaming-lambda)
- N/A (IAM Policy JSON, HCL configuration) + AWS IAM, S3, Terraform (018-tfstate-bucket-fix)
- S3 (Terraform state bucket) (018-tfstate-bucket-fix)
- Python 3.13 + None (stdlib `time` module only) (066-fix-latency-timing)
- N/A (in-memory latency tracking) (066-fix-latency-timing)
- YAML (GitHub Actions workflows, Dependabot config) + GitHub Dependabot service, dependabot/fetch-metadata@v2 action, GitHub CLI (gh) (067-dependabot-automerge-audit)
- N/A (configuration files only) (067-dependabot-automerge-audit)
- YAML (GitHub Actions workflow syntax), Bash (slash command) + GitHub Actions, GitHub CLI (`gh`), GitHub REST API (069-stale-pr-autoupdate)
- N/A (workflow configuration only) (069-stale-pr-autoupdate)
- Python 3.13 (existing project standard) + Semgrep (SAST), Bandit (Python security linter), pre-commit, Make (070-validation-blindspot-audit)
- N/A (tooling configuration only) (070-validation-blindspot-audit)

- **Python 3.13** with FastAPI, boto3, pydantic, aws-lambda-powertools, httpx
- **AWS Services**: DynamoDB (single-table design), S3, Lambda, SNS, EventBridge, Cognito, CloudFront
- **External APIs**: Tiingo (primary), Finnhub (secondary) for financial news sentiment
- **Email**: SendGrid (100/day free tier)
- **Bot Protection**: hCaptcha

## Project Structure

```text
src/
├── lambdas/
│   ├── dashboard/       # API endpoints (auth, configs, alerts, notifications)
│   ├── ingestion/       # Tiingo/Finnhub news ingestion
│   ├── analysis/        # Sentiment analysis + ATR calculation
│   ├── notification/    # Email alerts via SendGrid
│   └── shared/          # Models, middleware, utilities
│       ├── models/      # Pydantic models with DynamoDB serialization
│       ├── middleware/  # hCaptcha, rate limiting, security headers
│       ├── adapters/    # Tiingo/Finnhub API adapters
│       └── cache/       # Ticker symbol cache
tests/
├── unit/                # Mocked tests (moto, responses)
├── contract/            # API schema validation tests
├── integration/         # E2E tests with mocked AWS
└── e2e/                 # Full E2E with synthetic data
infrastructure/
└── terraform/
    └── modules/         # Lambda, DynamoDB, Cognito, CloudFront, etc.
```

## Commands

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/shared/middleware/test_rate_limit.py -v

# Run tests with coverage
pytest tests/unit/ --cov=src --cov-report=term-missing

# Format code (Ruff - migrated from Black in feat(057))
ruff format src/ tests/

# Lint code
ruff check src/ tests/

# Auto-fix lint issues
ruff check --fix src/ tests/

# Validate Terraform
cd infrastructure/terraform && terraform fmt -recursive && terraform validate
```

## Code Style

- Python 3.13: Follow PEP 8, use Ruff for formatting (Black removed in feat(057))
- Linting: Ruff (replaces flake8, isort - but NOT bandit)
- Line length: 88 characters (pragma comments excluded from limit)
- Configuration: pyproject.toml (single source of truth)
- Pragma audit: `make audit-pragma` validates # noqa and # nosec comments

## SAST (Static Application Security Testing)

Local security scanning runs before code reaches CI. Two-tier approach:

### Pre-commit: Bandit (fast, every commit)
```bash
# Runs automatically on commit via pre-commit hook
# Blocks HIGH and MEDIUM severity issues
# Config: pyproject.toml [tool.bandit]
bandit -c pyproject.toml -r src/ -ll
```

### Make validate: Semgrep (comprehensive, before push)
```bash
# Run as part of make validate or standalone
make sast                    # Run SAST only
make validate                # Full validation including SAST
```

### Common SAST Patterns Fixed in This Repo
- **Log injection (CWE-117)**: Use `sanitize_for_log()` from `src/lambdas/shared/logging_utils.py`
- **Clear-text logging (CWE-312)**: Never log sensitive data; use `redact_sensitive_fields()`
- **Hardcoded secrets (CWE-798)**: Use AWS Secrets Manager, never hardcode

### When SAST Flags Issues
1. Understand the vulnerability pattern (check CWE reference)
2. Fix with proper sanitization or redesign
3. Do NOT suppress without documented justification
4. Do NOT rename variables to avoid detection

## Git Commit Security Requirements

**CRITICAL SECURITY POLICY - NEVER BYPASS**:

1. **ALL commits MUST be GPG-signed** - Use `git commit -S` or `git commit --amend -S`
2. **NEVER use `--no-gpg-sign`** - This bypasses critical security verification
3. **If GPG signing fails**, this indicates a security configuration issue that MUST be fixed
4. **DO NOT attempt to bypass GPG failures** - Investigate and resolve the root cause

**Why This Matters**:
- GPG signatures verify commit authenticity and prevent impersonation
- Unsigned commits create security vulnerabilities in the supply chain
- GPG failures often indicate misconfiguration that could affect other security tools

**Correct Workflow**:
```bash
# Making commits
git commit -S -m "commit message"

# Amending commits
git commit --amend -S --no-edit

# If GPG fails - FIX IT, don't bypass it
# Check GPG configuration, verify key exists, ensure agent is running
```

**Test Environment Separation**:
- **LOCAL mirrors DEV**: Always uses mocked AWS resources (moto)
- **PREPROD mirrors PROD**: Always uses real AWS resources
- Preprod tests are excluded from local runs via pytest marker: `-m "not preprod"`
- Never attempt to run preprod tests locally - they require real AWS credentials

## Feature 006 Patterns

### DynamoDB Key Design (Single-Table)
```python
# User: pk="USER#{user_id}", sk="PROFILE"
# Configuration: pk="USER#{user_id}", sk="CONFIG#{config_id}"
# Alert Rule: pk="CONFIG#{config_id}", sk="ALERT#{alert_id}"
# Notification: pk="USER#{user_id}", sk="NOTIF#{timestamp}#{notification_id}"
# Magic Link Token: pk="TOKEN#{token}", sk="TOKEN"
# Rate Limit: pk="RATE#{client_ip}#{action}", sk="RATE"
# Circuit Breaker: pk="CB#{service}", sk="STATE"
# Quota Tracker: pk="QUOTA#{service}", sk="DAILY#{date}"
```

### Pydantic Model Pattern
All shared models in `src/lambdas/shared/models/` follow this pattern:
```python
class Configuration(BaseModel):
    config_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    name: str = Field(max_length=100)
    tickers: list[TickerConfig] = Field(max_length=5)

    @property
    def pk(self) -> str:
        return f"USER#{self.user_id}"

    @property
    def sk(self) -> str:
        return f"CONFIG#{self.config_id}"

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Serialize to DynamoDB item format."""

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "Configuration":
        """Deserialize from DynamoDB item format."""
```

### Middleware Usage
```python
from src.lambdas.shared.middleware import (
    add_security_headers,
    check_rate_limit,
    get_client_ip,
    verify_captcha,
)

# In handler:
client_ip = get_client_ip(event)
rate_result = check_rate_limit(table, client_ip, action="config_create")
if not rate_result.allowed:
    return add_security_headers({"statusCode": 429, "body": "..."})
```

### X-Ray Tracing Pattern
```python
from aws_xray_sdk.core import xray_recorder, patch_all
patch_all()  # After stdlib, before local imports

@xray_recorder.capture("function_name")
def my_function():
    pass
```

### Testing Patterns
- **Unit tests**: Use `moto` for DynamoDB, `responses` for HTTP mocking
- **Contract tests**: Validate API response schemas match `specs/006-*/contracts/*.md`
- **Integration tests**: Use `E2ETestContext` fixture with synthetic data generators
- **All external APIs mocked**: Tiingo, Finnhub, SendGrid, hCaptcha

## Feature 007 Frontend Patterns

### Tech Stack
- **Next.js 14** with App Router (`'use client'` directives)
- **shadcn/ui** (Tailwind + Radix primitives)
- **Zustand** for client state with persistence
- **React Query** (@tanstack/react-query) for server state
- **Framer Motion** for animations
- **Lightweight Charts** (TradingView) for sentiment charts
- **Vitest** for unit tests, **Playwright** for E2E

### Frontend Commands
```bash
cd frontend/

# Development
npm run dev              # Start dev server at localhost:3000
npm run build            # Production build
npm run typecheck        # TypeScript type checking

# Testing
npm test                 # Run unit tests (Vitest)
npm run test:watch       # Watch mode
npm run test:e2e         # Run E2E tests (Playwright)
npm run test:e2e:ui      # Playwright UI mode
```

### Component Patterns
```tsx
// Dynamic import for heavy components (reduces bundle size)
const SentimentChart = dynamic(
  () => import('@/components/charts/sentiment-chart').then((mod) => ({ default: mod.SentimentChart })),
  { loading: () => <ChartSkeleton />, ssr: false }
);

// Accessibility: All interactive elements need:
// - role, aria-label, tabIndex
// - keyboard handlers (Enter/Space)
// - focus-visible ring styling
```

### State Management
```tsx
// Zustand store with persistence
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const useStore = create(persist((set) => ({
  value: 'default',
  setValue: (value) => set({ value }),
}), { name: 'store-name' }));

// React Query for server state
const { data, isLoading } = useQuery({
  queryKey: ['configs'],
  queryFn: fetchConfigs,
});
```

### Testing Patterns
```tsx
// Mock framer-motion for unit tests
vi.mock('framer-motion', () => ({
  motion: { div: (props) => <div {...props} /> },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

// Mock zustand stores
vi.mock('@/stores/auth-store', () => ({
  useAuthStore: vi.fn(() => ({ user: mockUser })),
}));
```

## Feature 016 SSE Lambda Patterns

### Two-Lambda Architecture
The project uses two Lambdas for different concerns:
- **Dashboard Lambda**: REST APIs with BUFFERED invoke mode (Mangum adapter)
- **SSE Lambda**: Streaming with RESPONSE_STREAM invoke mode (AWS Lambda Web Adapter)

```text
src/lambdas/
├── dashboard/           # REST APIs (BUFFERED mode via Mangum)
│   ├── handler.py       # FastAPI app wrapped with Mangum
│   └── ...
└── sse_streaming/       # SSE streaming (RESPONSE_STREAM mode via Lambda Web Adapter)
    ├── Dockerfile       # Docker image with Lambda Web Adapter
    ├── handler.py       # FastAPI app with SSE endpoints
    ├── connection.py    # Thread-safe ConnectionManager
    ├── stream.py        # SSE event generators
    ├── polling.py       # DynamoDB polling service
    ├── config.py        # Configuration lookup service
    ├── models.py        # SSE event models (Pydantic)
    └── metrics.py       # CloudWatch metrics helper
```

### SSE Lambda Commands
```bash
# Run SSE streaming unit tests
PYTHONPATH=. pytest tests/unit/sse_streaming/ -v

# Run specific SSE test file
PYTHONPATH=. pytest tests/unit/sse_streaming/test_connection.py -v

# Run E2E SSE tests (requires preprod)
pytest tests/e2e/test_sse.py -v -m preprod

# Local development (requires Docker)
cd src/lambdas/sse_streaming
docker build -t sse-lambda .
docker run -p 8080:8080 -e AWS_LAMBDA_FUNCTION_NAME=local sse-lambda
```

### SSE Endpoint Patterns
```python
# Global stream (public, no auth)
@app.get("/api/v2/stream")
async def global_stream(request: Request):
    # Available to all users, broadcasts all metrics
    return EventSourceResponse(sse_event_generator(connection))

# Config-specific stream (requires X-User-ID header)
@app.get("/api/v2/configurations/{config_id}/stream")
async def config_stream(
    request: Request,
    config_id: str,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    # Validates X-User-ID (401 if missing)
    # Validates config ownership (404 if not found)
    # Filters events to config's tickers only
    return EventSourceResponse(sse_event_generator(connection, ticker_filters))

# Stream status (connection info)
@app.get("/api/v2/stream/status")
async def stream_status():
    return {"connections": count, "max_connections": 100, "available": 100 - count}
```

### Connection Management
```python
from src.lambdas.sse_streaming.connection import connection_manager

# Thread-safe connection tracking (100 max per Lambda instance)
connection = connection_manager.add_connection(config_id, ticker_filters)
try:
    async for event in sse_event_generator(connection):
        yield event
finally:
    connection_manager.remove_connection(connection.connection_id)
```

### SSE Event Models
```python
# Event types: heartbeat, metrics, sentiment_update
from src.lambdas.sse_streaming.models import (
    HeartbeatData,      # {"type": "heartbeat", "timestamp": "..."}
    MetricsEventData,   # {"type": "metrics", "total": N, ...}
    SentimentUpdateData # {"type": "sentiment_update", "ticker": "...", ...}
)
```

### Testing SSE Endpoints
**IMPORTANT**: FastAPI's TestClient hangs on SSE endpoints because streams never complete. Use these patterns:

```python
# DON'T: Hit SSE endpoint directly (causes hanging)
# response = client.get("/api/v2/stream")  # HANGS FOREVER!

# DO: Test route registration instead
from starlette.routing import Route
from src.lambdas.sse_streaming.handler import app

def test_global_stream_endpoint_registered():
    stream_route = None
    for route in app.routes:
        if isinstance(route, Route) and route.path == "/api/v2/stream":
            stream_route = route
            break
    assert stream_route is not None
    assert "GET" in stream_route.methods

# DO: Test non-streaming endpoints normally
def test_stream_status():
    client = TestClient(app)
    response = client.get("/api/v2/stream/status")
    assert response.status_code == 200

# DO: Test error responses (non-streaming)
def test_config_stream_requires_auth():
    client = TestClient(app)
    response = client.get("/api/v2/configurations/test/stream")
    assert response.status_code == 401  # Returns immediately (not streaming)
```

### Frontend SSE Integration
```javascript
// config.js - Two-Lambda architecture
const CONFIG = {
    API_BASE_URL: '',      // Dashboard Lambda (REST)
    SSE_BASE_URL: '',      // SSE Lambda (streaming) - set in production
    ENDPOINTS: {
        STREAM: '/api/v2/stream'
    }
};

// app.js - Use SSE_BASE_URL for streaming
const baseUrl = CONFIG.SSE_BASE_URL || CONFIG.API_BASE_URL;
const streamUrl = `${baseUrl}${CONFIG.ENDPOINTS.STREAM}`;
const eventSource = new EventSource(streamUrl);
```

## Recent Changes
- 057-pragma-comment-stability: Added [if applicable, e.g., PostgreSQL, CoreData, files or N/A]
- 070-validation-blindspot-audit: Added Python 3.13 (existing project standard) + Semgrep (SAST), Bandit (Python security linter), pre-commit, Make
- 069-stale-pr-autoupdate: Added YAML (GitHub Actions workflow syntax), Bash (slash command) + GitHub Actions, GitHub CLI (`gh`), GitHub REST API

<!-- MANUAL ADDITIONS START -->

## GitHub CLI Setup

Install gh CLI for checking CI results and managing PRs:

```bash
# Install to local bin (no sudo required)
mkdir -p ~/.local/bin
curl -sL https://github.com/cli/cli/releases/download/v2.40.1/gh_2.40.1_linux_amd64.tar.gz | tar xz -C /tmp
mv /tmp/gh_2.40.1_linux_amd64/bin/gh ~/.local/bin/
export PATH="$HOME/.local/bin:$PATH"

# One-time authentication
gh auth login
```

**Auth login steps:**
1. Where do you use GitHub? → `GitHub.com`
2. Preferred protocol? → `HTTPS`
3. Authenticate Git with credentials? → `Yes`
4. How to authenticate? → `Login with a web browser`

A one-time code will appear (8 characters). Copy just the code itself, then paste it in the browser when prompted.

```bash
# Check CI workflow runs
gh run list --repo traylorre/sentiment-analyzer-gsk --limit 5

# View specific run details
gh run view <run-id> --repo traylorre/sentiment-analyzer-gsk
```

## Terraform Backend Setup (One-Time)

Before CI/CD deploys will work, you must set up the Terraform state backend:

```bash
# 1. Create the S3 bucket and DynamoDB table for state
cd infrastructure/terraform/bootstrap
terraform init
terraform apply

# 2. Note the bucket name from output
terraform output state_bucket_name

# 3. Update main.tf with your bucket name
# Edit infrastructure/terraform/main.tf and replace
# "sentiment-analyzer-terraform-state-YOUR_ACCOUNT_ID" with the actual bucket name

# 4. Initialize main terraform with S3 backend
cd ../
terraform init

# 5. Import existing secrets (if they exist in AWS)
terraform import -var="environment=dev" module.secrets.aws_secretsmanager_secret.newsapi dev/sentiment-analyzer/newsapi
terraform import -var="environment=dev" module.secrets.aws_secretsmanager_secret.dashboard_api_key dev/sentiment-analyzer/dashboard-api-key

# 6. Verify everything is in state
terraform plan -var="environment=dev"
```

After this setup, CI/CD deployments will persist state in S3 and won't recreate existing resources.

## Terraform State Management

### How State Locking Works

Terraform uses **S3 native locking** to prevent concurrent modifications. Lock files are stored as `.tflock` files directly in the S3 state bucket. The CI/CD pipeline handles most lock scenarios automatically:

1. **Concurrency control**: Only one deployment runs at a time (GitHub Actions `concurrency` group)
2. **Lock timeout**: Terraform waits up to 5 minutes for locks to be released (`-lock-timeout=5m`)
3. **Lock detection**: CI checks for existing lock files before each deploy and provides guidance
4. **Automatic cleanup**: Terraform removes lock files when operations complete normally

### Best Practices

- **Never run terraform locally while CI is deploying** - This causes lock conflicts
- **Don't cancel running deploy workflows** - This may leave orphaned lock files
- **Use the GitHub Actions UI** to trigger deploys, not local terraform

### Manual State Lock Recovery

If a lock file is orphaned, you can manually unlock:

```bash
cd infrastructure/terraform
terraform init

# Get the Lock ID from the error message or workflow logs, then:
terraform force-unlock <LOCK_ID>

# Example:
terraform force-unlock 4a2b102d-2da5-6055-25d4-0aa01be88bbb
```

Or delete the lock file directly via AWS CLI:

```bash
# For preprod
aws s3 rm s3://sentiment-analyzer-terraform-state-218795110243/preprod/terraform.tfstate.tflock

# For prod
aws s3 rm s3://sentiment-analyzer-terraform-state-218795110243/prod/terraform.tfstate.tflock
```

### Checking Lock Status

```bash
# Check for preprod lock file
aws s3api head-object \
  --bucket sentiment-analyzer-terraform-state-218795110243 \
  --key preprod/terraform.tfstate.tflock

# Check for prod lock file
aws s3api head-object \
  --bucket sentiment-analyzer-terraform-state-218795110243 \
  --key prod/terraform.tfstate.tflock
```

<!-- MANUAL ADDITIONS END -->
