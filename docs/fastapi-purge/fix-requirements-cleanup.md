# Fix: Remove Packages from Requirements

**Parent:** [HL-fastapi-purge-checklist.md](./HL-fastapi-purge-checklist.md)
**Priority:** P7
**Status:** [ ] TODO
**Depends On:** All code migration tasks (P2-P6)

---

## Problem Statement

After all code has been migrated away from FastAPI/Mangum, remove the dead packages from all requirements files. Do this LAST to avoid breaking code during migration.

---

## Packages to Remove

| Package | Why Remove | Transitive Deps Also Removed |
|---------|-----------|------------------------------|
| `fastapi` | No longer imported | `starlette`, `anyio` (if not used elsewhere) |
| `mangum` | No longer imported | None (standalone) |
| `uvicorn` | Dev-only ASGI server, no longer needed | `h11`, `httptools` (if present) |
| `starlette` | Transitive via FastAPI, no direct use | `anyio` |

---

## Requirements Files to Update

- [ ] `requirements.txt` - Production dependencies
- [ ] `requirements-ci.txt` - CI dependencies
- [ ] `requirements-dev.txt` - Development dependencies
- [ ] `pyproject.toml` - If dependencies listed there

---

## Pre-Removal Verification

```bash
# Confirm no remaining imports BEFORE removing packages
grep -rn "import fastapi\|from fastapi\|import mangum\|from mangum" src/ tests/
grep -rn "import uvicorn\|from uvicorn\|import starlette\|from starlette" src/ tests/

# Should return 0 results
```

---

## Post-Removal Verification

```bash
# Reinstall from clean state
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests to verify nothing breaks
pytest tests/unit/ -v

# Check for import errors
python -c "from src.lambdas.dashboard.ohlc import lambda_handler; print('OK')"
```

---

## Dockerfile Update

If the dashboard Lambda is container-based, the Dockerfile may `pip install` from requirements:

```dockerfile
# Verify Dockerfile references correct requirements file
COPY requirements.txt .
RUN pip install -r requirements.txt
```

No Dockerfile change needed unless it has a separate `COPY` for specific packages.

---

## Size Reduction Estimate

| Package | Installed Size |
|---------|---------------|
| fastapi | ~3MB |
| mangum | ~0.5MB |
| uvicorn | ~2MB |
| starlette | ~3MB |
| **Total** | **~8-15MB** (with transitive deps) |

---

## Files to Modify

| File | Change |
|------|--------|
| `requirements.txt` | Remove fastapi, mangum, uvicorn |
| `requirements-ci.txt` | Remove same |
| `requirements-dev.txt` | Remove same |
| `Dockerfile` (if exists) | Verify still builds |

---

## Related

- [audit-fastapi-surface.md](./audit-fastapi-surface.md) - Confirms no remaining imports
- [fix-validation-smoketest.md](./fix-validation-smoketest.md) - Verify clean install works
