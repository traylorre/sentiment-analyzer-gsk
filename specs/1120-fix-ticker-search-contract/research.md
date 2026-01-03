# Research: Fix Ticker Search API Contract

**Feature**: 1120-fix-ticker-search-contract
**Date**: 2026-01-02

## Research Questions

### Q1: What is the correct API response format from the backend?

**Decision**: Backend returns `TickerSearchResponse` with wrapped `{results: [...]}` structure

**Rationale**:
- Backend `tickers.py:48-51` defines `TickerSearchResponse` with `results: list[TickerSearchResult]`
- Router returns `result.model_dump()` which produces `{"results": [...]}`
- This is RESTful best practice - wrapping arrays allows future extensibility (pagination, metadata)

**Source**: `src/lambdas/dashboard/tickers.py`, `src/lambdas/dashboard/router_v2.py:1189-1201`

### Q2: What does the frontend currently expect?

**Decision**: Frontend expects bare array `TickerSearchResult[]`

**Rationale**:
- `frontend/src/lib/api/tickers.ts:19-22` defines: `api.get<TickerSearchResult[]>('/api/v2/tickers/search', ...)`
- TypeScript expects the response body to be an array directly
- When backend returns `{results: [...]}`, the frontend receives an object but treats it as an array
- Calling `.map()` or `.length` on the "array" fails silently or returns unexpected results

**Source**: `frontend/src/lib/api/tickers.ts:19-22`

### Q3: What is the recommended fix approach?

**Decision**: Update frontend to unwrap the `results` field

**Rationale**:
- Backend API is correctly designed (wrapped response is best practice)
- Frontend change is isolated to a single file
- Adding a response type interface maintains type safety
- This approach requires no backend changes

**Pattern**:
```typescript
// Current (broken):
search: (query: string, limit?: number) =>
  api.get<TickerSearchResult[]>('/api/v2/tickers/search', { params: { q: query, limit } }),

// Fixed:
interface TickerSearchResponse {
  results: TickerSearchResult[];
}

search: (query: string, limit?: number) =>
  api.get<TickerSearchResponse>('/api/v2/tickers/search', { params: { q: query, limit } })
    .then(response => response.results),
```

## Alternatives Rejected

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Modify backend to return bare array | Violates RESTful best practices, removes extensibility |
| Add middleware to transform response | Over-engineering for simple fix |
| Use any type and cast | Loses type safety |

## Conclusion

Single-line change in `tickers.ts` to add response unwrapping. Maintains type safety and follows frontend patterns.
