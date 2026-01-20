# Source Code Directory

## Structure

```
src/
├── lambdas/           # AWS Lambda function handlers
│   ├── ingestion/     # Tiingo + Finnhub financial news ingestion (EventBridge triggered)
│   ├── analysis/      # Sentiment analysis (SNS triggered)
│   ├── dashboard/     # FastAPI dashboard (Function URL)
│   └── shared/        # Common utilities (DynamoDB, Secrets, schemas)
├── lib/               # Shared libraries (deduplication, metrics)
└── dashboard/         # Static UI files (HTML/CSS/JS)
```

## For On-Call Engineers

If you're here during an incident:

1. **Ingestion failures** → Check `lambdas/ingestion/handler.py`
   - Tiingo/Finnhub rate limits: Look for `RATE_LIMIT_EXCEEDED` errors
   - Secret issues: Check `shared/secrets.py` caching logic

2. **Analysis failures** → Check `lambdas/analysis/handler.py`
   - Model loading: Look for `/opt/model` path issues
   - DynamoDB updates: Check conditional expressions in handler

3. **Dashboard issues** → Check `lambdas/dashboard/handler.py`
   - API key validation: Look for `compare_digest` calls
   - API v2 endpoints: Check `/api/v2/*` routes

See `docs/operations/FAILURE_RECOVERY_RUNBOOK.md` for full runbooks.

## For Developers

- All Lambda handlers follow the same pattern: `lambda_handler(event, context)`
- Shared code in `shared/` is tested independently with moto mocks
- Use `lib/` for non-Lambda-specific utilities

## Security Notes

- API keys retrieved via Secrets Manager (never hardcoded)
- All external calls use HTTPS
- Input validation via Pydantic schemas
