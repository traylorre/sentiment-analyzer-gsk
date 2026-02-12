# Audit: FastAPI Surface Area

**Parent:** [HL-fastapi-purge-checklist.md](./HL-fastapi-purge-checklist.md)
**Priority:** P0 (Must complete first)
**Status:** [ ] TODO

---

## Objective

Catalog every FastAPI/Mangum touchpoint in the codebase before cutting anything. This audit drives all subsequent tasks.

---

## Audit Checklist

### Imports
- [ ] Find all `from fastapi import ...` statements
- [ ] Find all `from mangum import ...` statements
- [ ] Find all `from starlette import ...` statements
- [ ] Find all `import uvicorn` statements
- [ ] Find transitive imports (files that import modules that import FastAPI)

### Routes
- [ ] Catalog all `@app.get()`, `@app.post()`, `@app.put()`, `@app.delete()` decorators
- [ ] Catalog all `@router.get()` etc. decorators
- [ ] Catalog all `app.include_router()` calls
- [ ] Document path parameters (e.g., `{ticker}`)
- [ ] Document query parameters (e.g., `Query(default=...)`)

### Middleware
- [ ] Catalog all `@app.middleware("http")` decorators
- [ ] Catalog all `app.add_middleware()` calls
- [ ] Document what each middleware does (timing, logging, CORS, X-Ray)

### Dependency Injection
- [ ] Catalog all `Depends()` usage
- [ ] Document what each dependency provides
- [ ] Identify singleton vs per-request dependencies

### Error Handling
- [ ] Catalog all `@app.exception_handler()` decorators
- [ ] Document custom exception classes used with FastAPI
- [ ] Identify HTTPException usage patterns

### Response Models
- [ ] Catalog all `response_model=...` parameters
- [ ] Document Pydantic models used for response serialization
- [ ] Identify custom Response subclasses

### App Configuration
- [ ] Document `app = FastAPI(...)` constructor parameters
- [ ] Document CORS origins configuration
- [ ] Document any OpenAPI/docs configuration

---

## Output Format

Produce a table per category:

```markdown
| File:Line | Pattern | Detail |
|-----------|---------|--------|
| main.py:5 | import | `from fastapi import FastAPI, Query` |
| main.py:12 | route | `@app.get("/api/v2/tickers/{ticker}/ohlc")` |
```

---

## Verification

```bash
# Quick validation commands
grep -rn "fastapi\|mangum\|starlette\|uvicorn" src/ --include="*.py"
grep -rn "Depends\|Query\|HTTPException" src/ --include="*.py"
grep -rn "TestClient" tests/ --include="*.py"
```

---

## Related

- [design-native-handler.md](./design-native-handler.md) - Uses audit output to design replacement
- [fix-test-migration.md](./fix-test-migration.md) - Uses audit output to map test changes
