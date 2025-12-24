# Tasks: Dashboard OHLC Integration

**Feature ID**: 1038
**Input**: spec.md, plan.md

## Phase 1: Component Integration

- [ ] T001 Update imports: add PriceSentimentChart, remove SentimentChart dynamic import in frontend/src/app/(dashboard)/page.tsx
- [ ] T002 Remove generateMockData function and TickerData interface with embedded data in frontend/src/app/(dashboard)/page.tsx
- [ ] T003 Simplify tickers state to only track symbols (no embedded data) in frontend/src/app/(dashboard)/page.tsx
- [ ] T004 Replace SentimentChart with PriceSentimentChart, passing activeTicker as ticker prop in frontend/src/app/(dashboard)/page.tsx
- [ ] T005 Remove refresh button logic (chart handles its own data) in frontend/src/app/(dashboard)/page.tsx

## Phase 2: State Cleanup

- [ ] T006 Update handleTickerSelect to only add symbol to list (no mock data generation) in frontend/src/app/(dashboard)/page.tsx
- [ ] T007 Update tickerChips useMemo to work with simplified state in frontend/src/app/(dashboard)/page.tsx

## Phase 3: Testing

- [ ] T008 Add unit test for PriceSentimentChart integration in frontend/src/__tests__/app/(dashboard)/page.test.tsx
- [ ] T009 Run make validate to verify no regressions

## Dependencies

- T001 must complete before T002-T005
- T006-T007 can run in parallel with T004-T005
- T008 depends on T001-T007 completion
- T009 runs last

## Parallel Opportunities

**Parallel Set 1**: After T001 completes
- T002, T003 (independent cleanup)

**Parallel Set 2**: After basic integration
- T006, T007 (state cleanup)

## Estimated Complexity

- **Low**: This is primarily removing code and swapping one component for another
- **Total**: ~100 lines changed (mostly deletions)
