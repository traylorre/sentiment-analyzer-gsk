# Feature 1303: Tasks

### T1: Replace _get_header in integration/ohlc/test_happy_path.py
1. Remove local `_get_header()` (lines 32-42)
2. Import `get_response_header` from conftest
3. Replace all `_get_header()` calls
4. Fix `is not None` → `!= ""` if needed

### T2: Verify OHLC tests pass
Run `pytest tests/integration/ohlc/ -v`

## Adversarial Review #3

**Lowest risk change in this battleplan.** Single file, well-understood function.
**READY FOR IMPLEMENTATION.**
