# Interview Demo Kit

Interactive tools for demonstrating the Sentiment Analyzer architecture during technical interviews.

## Quick Start

1. **Open the Dashboard**
   ```bash
   # From project root
   open interview/index.html
   # Or use Python's http server
   cd interview && python -m http.server 8080
   ```

2. **Run Traffic Generator**
   ```bash
   cd interview
   python traffic_generator.py --env preprod --scenario all
   ```

## Components

### `index.html` - Interactive Dashboard

A single-page web app with:
- **Environment Toggle**: Switch between preprod/prod
- **Interview Timer**: Track time with color warnings at 60/75/85 minutes
- **Live API Demos**: Execute real API calls from the browser
- **Architecture Walkthrough**: Visual timeline and diagrams

**Keyboard Shortcuts:**
- `Ctrl/Cmd + 1-9`: Jump to sections

### `traffic_generator.py` - Synthetic Traffic

Generates realistic traffic patterns to demonstrate system behavior.

**Scenarios:**

| Scenario | Command | What It Shows |
|----------|---------|---------------|
| Basic Flow | `--scenario basic` | Happy path: session → config → sentiment |
| Cache Warmup | `--scenario cache` | Cold vs warm latency (~200ms → ~50ms) |
| Load Test | `--scenario load` | Concurrent users, horizontal scaling |
| Rate Limit | `--scenario rate-limit` | Burst traffic, 429 responses |
| All | `--scenario all` | Full demonstration |

**Example:**
```bash
# Run all scenarios with verbose output
python traffic_generator.py --env preprod --scenario all

# Custom load test
python traffic_generator.py --env preprod --scenario load --users 10 --requests 20
```

## Interview Flow (90 minutes)

### Phase 1: Overview (10 min)
1. Open Welcome section
2. Start interview timer
3. Show live health stats
4. Click "Start the Tour"

### Phase 2: Architecture Deep Dive (30 min)
1. **Architecture**: Data flow pipeline, single-table DynamoDB
2. **Authentication**: Anonymous → Magic Link → OAuth flow
3. **Configurations**: Business rules, soft deletes
4. **Sentiment Analysis**: Multi-source aggregation

### Phase 3: Resilience Patterns (25 min)
1. **External APIs**: Adapter pattern, quota tracking
2. **Circuit Breaker**: Live state machine demo
3. **Caching Strategy**: 5-layer cache architecture
4. Run `traffic_generator.py --scenario cache` in terminal

### Phase 4: Operations & Testing (15 min)
1. **Observability**: Structured logging, X-Ray tracing
2. **Testing**: Pyramid, oracle-based validation
3. **Infrastructure**: Terraform modules, cost optimization

### Phase 5: Q&A & Code Review (10 min)
1. Open specific code files as needed
2. Show test files
3. Walk through Terraform modules

## Talking Points

### Cost Efficiency
- "~$2.50/month for dev environment"
- "DynamoDB on-demand = pay per request"
- "Lambda 128MB minimum = ~$0.0000002 per invocation"

### Caching ROI
- "Circuit breaker cache: 90% DynamoDB read reduction"
- "Quota tracker: 95% read reduction with batched writes"
- "Total cost impact: est. $50-100/month savings at scale"

### Circuit Breaker Design
- "5 failures = OPEN (protects downstream)"
- "60 second timeout = cooldown period"
- "HALF-OPEN = single probe request to test recovery"

### Testing Philosophy
- "1,230+ unit tests = fast feedback (<30s)"
- "Moto for DynamoDB = no real AWS costs in CI"
- "E2E with synthetic data = realistic validation"
