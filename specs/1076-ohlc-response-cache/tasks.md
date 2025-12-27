# Implementation Tasks: OHLC Response Cache

**Feature Branch**: `1076-ohlc-response-cache`
**Created**: 2025-12-27
**Plan**: [plan.md](./plan.md)

## Tasks

- [ ] **Task 1**: Add cache configuration constants (TTLs, max entries)
- [ ] **Task 2**: Add cache storage dicts and stats tracking
- [ ] **Task 3**: Add `_get_ohlc_cache_key()` function
- [ ] **Task 4**: Add `_get_cached_ohlc()` function with TTL check
- [ ] **Task 5**: Add `_set_cached_ohlc()` function with LRU eviction
- [ ] **Task 6**: Add `get_ohlc_cache_stats()` function
- [ ] **Task 7**: Integrate cache check at start of `get_ohlc()` handler
- [ ] **Task 8**: Integrate cache set before returning success response
- [ ] **Task 9**: Add unit tests for cache functionality
- [ ] **Task 10**: Run all OHLC tests to verify no regressions
