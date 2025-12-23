# Quickstart Guide

Feature-1021 | Dashboard Resolution Config

## Prerequisites

- Node.js (for serving static files)
- Python 3.13 (for running tests)

## Verify Configuration

After implementation, verify the config in browser console:

```javascript
// Open dashboard and run in browser console:
console.log(CONFIG.RESOLUTIONS);
// Should show 8 resolution objects

console.log(CONFIG.DEFAULT_RESOLUTION);
// Should show "5m"

console.log(CONFIG.ENDPOINTS.TIMESERIES);
// Should show "/api/v2/timeseries"

console.log(CONFIG.RESOLUTION_ORDER);
// Should show ["1m", "5m", "10m", "1h", "3h", "6h", "12h", "24h"]
```

## Run Unit Tests

```bash
cd /home/traylorre/projects/sentiment-analyzer-gsk
python -m pytest tests/unit/dashboard/test_config.py -v
```

## Validate TTL Alignment

The unit test compares JavaScript config TTLs against Python model values:

```bash
python -m pytest tests/unit/dashboard/test_config.py::TestResolutionConfig::test_ttl_matches_python_model -v
```

## Common Issues

### Issue: CONFIG.RESOLUTIONS undefined

**Cause**: Script loaded before config.js
**Fix**: Ensure config.js is loaded first in HTML

### Issue: Cannot modify frozen config

**Expected behavior**: Config is intentionally frozen. Use spread operator to create copies:

```javascript
const myConfig = { ...CONFIG.RESOLUTIONS["5m"] };
myConfig.customField = "value";  // OK
```

### Issue: Endpoint 404

**Cause**: Backend doesn't have /api/v2/timeseries endpoint yet
**Note**: This feature only adds frontend config; backend endpoint is separate feature
