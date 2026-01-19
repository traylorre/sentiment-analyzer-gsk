# Demo URLs for Interview (LOCAL - DO NOT COMMIT)

## Quick Access

**Main Dashboard (Browser):**
https://cjx6qw4a7xqw6cuifvkbi6ae2e0evviw.lambda-url.us-east-1.on.aws/

**API Docs:**
https://cjx6qw4a7xqw6cuifvkbi6ae2e0evviw.lambda-url.us-east-1.on.aws/docs

**OAuth URLs (GET - no auth):**
https://cjx6qw4a7xqw6cuifvkbi6ae2e0evviw.lambda-url.us-east-1.on.aws/api/v2/auth/oauth/urls

---

## API Base URL

```
API=https://cjx6qw4a7xqw6cuifvkbi6ae2e0evviw.lambda-url.us-east-1.on.aws
```

---

## Terminal Demo Script

```bash
API="https://cjx6qw4a7xqw6cuifvkbi6ae2e0evviw.lambda-url.us-east-1.on.aws"

# 1. Get anonymous token (POST required)
TOKEN=$(curl -s -X POST "$API/api/v2/auth/anonymous" \
  -H "Content-Type: application/json" -d '{}' | jq -r .token)
echo "Token: $TOKEN"

# 2. Create a configuration
curl -s -X POST "$API/api/v2/configurations" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Interview Demo","tickers":[{"symbol":"AAPL"}]}'

# 3. List configurations
curl -s "$API/api/v2/configurations" \
  -H "Authorization: Bearer $TOKEN" | jq

# 4. Get sentiment for a config (replace CONFIG_ID)
curl -s "$API/api/v2/configurations/{CONFIG_ID}/sentiment" \
  -H "Authorization: Bearer $TOKEN" | jq
```

---

## Available Endpoints

### Public (no auth)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | HTML Dashboard UI |
| GET | `/docs` | FastAPI Swagger docs |
| POST | `/api/v2/auth/anonymous` | Get session token |
| GET | `/api/v2/auth/oauth/urls` | OAuth provider URLs |
| GET | `/api/v2/auth/magic-link/verify` | Verify magic link |

### Authenticated (Bearer token required)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/configurations` | List user configs |
| POST | `/api/v2/configurations` | Create config |
| GET | `/api/v2/configurations/{id}` | Get config |
| DELETE | `/api/v2/configurations/{id}` | Delete config |
| GET | `/api/v2/configurations/{id}/sentiment` | Get sentiment data |
| GET | `/api/v2/configurations/{id}/heatmap` | Get heatmap data |
| GET | `/api/v2/configurations/{id}/volatility` | Get volatility data |
| GET | `/api/v2/auth/session` | Current session info |
| POST | `/api/v2/auth/signout` | End session |

---

## GitHub URLs

- **Repository:** https://github.com/traylorre/sentiment-analyzer-gsk
- **Latest PR:** https://github.com/traylorre/sentiment-analyzer-gsk/pull/207
- **CI/CD:** https://github.com/traylorre/sentiment-analyzer-gsk/actions
- **Terraform:** https://github.com/traylorre/sentiment-analyzer-gsk/tree/main/infrastructure/terraform

---

## Architecture Highlights

- **Serverless**: AWS Lambda (Python 3.13)
- **Database**: DynamoDB single-table design
- **Frontend**: AWS Amplify (Next.js SSR)
- **Auth**: Anonymous, Magic Link, OAuth (Google/GitHub)
- **External APIs**: Tiingo, Finnhub
- **CI/CD**: GitHub Actions with GPG-signed commits

---

*Generated: 2025-11-29*
