# Research: Fix Lambda ZIP Packaging Structure

**Feature**: 427-fix-lambda-zip-packaging
**Date**: 2025-12-18

## Summary

This fix applies an existing pattern (dashboard Lambda) to broken Lambdas. Minimal research required.

## Decision: Apply Dashboard Pattern

**Decision**: Use the dashboard Lambda packaging pattern for all ZIP-based Lambdas.

**Rationale**:
1. Dashboard Lambda works correctly in production
2. Same handler import structure (`src.lambdas.X.handler.lambda_handler`)
3. No code changes required - only workflow configuration
4. Already validated by existing E2E tests

**Alternatives Considered**:

| Alternative | Rejected Because |
|-------------|------------------|
| Convert to relative imports | Breaks local development, requires code changes |
| Use Lambda layers | Overkill for 6 Lambdas, adds complexity |
| Flat imports with PYTHONPATH | Doesn't fix the core structure issue |

## Canonical Sources

- AWS Lambda Python packaging: https://docs.aws.amazon.com/lambda/latest/dg/python-package.html
- AWS Lambda troubleshooting: https://docs.aws.amazon.com/lambda/latest/dg/troubleshooting-deployment.html
- AWS Lambda handler naming: https://docs.aws.amazon.com/lambda/latest/dg/python-handler.html

## Findings

### Dashboard Lambda (CORRECT)

```yaml
# Lines 219-228 in deploy.yml
mkdir -p packages/dashboard-build/src/lambdas/dashboard packages/dashboard-build/src/lib
cp -r packages/dashboard-deps/* packages/dashboard-build/
cp -r src/lambdas/dashboard/* packages/dashboard-build/src/lambdas/dashboard/
cp -r src/lambdas/shared packages/dashboard-build/src/lambdas/
cp -r src/lib/* packages/dashboard-build/src/lib/
```

**Result**: Handler imports `from src.lambdas.dashboard.X` work because files are at `src/lambdas/dashboard/X.py` in ZIP.

### Ingestion Lambda (BROKEN)

```yaml
# Lines 154-159 in deploy.yml
mkdir -p packages/ingestion-build/src/lambdas packages/ingestion-build/src/lib
cp -r packages/ingestion-deps/* packages/ingestion-build/
cp -r src/lambdas/ingestion/* packages/ingestion-build/           # WRONG
cp -r src/lambdas/shared packages/ingestion-build/src/lambdas/
cp -r src/lib/* packages/ingestion-build/src/lib/
```

**Result**: Handler imports `from src.lambdas.ingestion.X` fail because files are at `X.py` (root), not `src/lambdas/ingestion/X.py`.

## No Further Research Needed

The fix is straightforward:
1. Identify all Lambdas with flat copy patterns
2. Apply dashboard pattern (structured copy)
3. Validate with docker-import validator
4. Test Lambda invocation
