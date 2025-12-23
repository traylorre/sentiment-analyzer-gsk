# Implementation Plan

Feature-1021 | Dashboard Resolution Config

## Technical Context

| Dimension | Value |
|-----------|-------|
| Language | JavaScript (ES6+) |
| Target File | src/dashboard/config.js |
| Dependencies | None (static config) |
| Testing | Unit test for config validation |
| Platform | Browser (Chrome, Firefox, Safari) |

## Constitution Check

| Section | Gate | Status |
|---------|------|--------|
| Section 5 | IaC for infrastructure changes | N/A (frontend only) |
| Section 6 | Observability for new components | N/A (config only) |
| Section 7 | Integration tests for AWS resources | N/A (no AWS) |
| Section 10 | Local SAST before push | PASS (pre-commit) |

**Result: 4/4 PASS** (N/A gates don't apply to frontend config changes)

## Implementation Approach

### Phase 0: Research

No research needed - resolution values are defined in `src/lib/timeseries/models.py`.

### Phase 1: Add Resolution Configuration

1. Add RESOLUTIONS object after existing config
2. Add RESOLUTION_ORDER array for UI display
3. Add DEFAULT_RESOLUTION constant
4. Add TIMESERIES endpoint
5. Freeze new config objects

### Phase 2: Unit Test

1. Create test to verify resolution values match Python models
2. Test immutability of config objects
3. Test endpoint format

## File Changes

| File | Change Type | Description |
|------|-------------|-------------|
| src/dashboard/config.js | Modify | Add RESOLUTIONS, TIMESERIES endpoint |
| tests/unit/dashboard/test_config.py | Create | Validate config values |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| TTL mismatch with server | Low | Medium | Unit test comparing to Python values |
| Breaking existing code | Low | High | Add new config, don't modify existing |
| Config mutation | Low | Medium | Object.freeze() |

## Alternatives Considered

1. **Dynamic config from API**: Rejected - adds latency, fails offline
2. **Shared JSON config file**: Rejected - requires build pipeline changes
3. **Generate from Python**: Rejected - over-engineering for 8 values

## Quickstart

See [quickstart.md](quickstart.md) for running and testing.
