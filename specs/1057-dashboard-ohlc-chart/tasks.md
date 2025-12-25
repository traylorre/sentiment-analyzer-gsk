# Tasks: Add OHLC Chart to Vanilla JS Dashboard

**Feature ID**: 1057
**Input**: spec.md

## Phase 1: Configuration Setup

- [x] T001 Add OHLC endpoint config to src/dashboard/config.js
- [x] T002 Add OHLC resolution mapping (backend values to display labels)

## Phase 2: HTML Structure

- [x] T003 Add OHLC chart container section to index.html (before or after timeseries)
- [x] T004 Add resolution selector button group HTML
- [x] T005 Add OHLC chart canvas element
- [x] T006 Add fallback message div for resolution fallback display

## Phase 3: Styles

- [x] T007 Add OHLC chart container styles to styles.css
- [x] T008 Add resolution selector button styles (match existing resolution selector pattern)
- [x] T009 Add candlestick chart specific styles (green/red candles)

## Phase 4: JavaScript Implementation

- [x] T010 Create src/dashboard/ohlc.js with OHLCChart class
- [x] T011 Implement loadOHLCData() method calling /api/v2/tickers/{ticker}/ohlc
- [x] T012 Implement resolution selector event handlers
- [x] T013 Implement Chart.js candlestick chart rendering
- [x] T014 Add sessionStorage persistence for resolution preference
- [x] T015 Handle API error states (401, 404, timeout)
- [x] T016 Display fallback message when resolution_fallback is true

## Phase 5: Integration

- [x] T017 Import ohlc.js in index.html script tags
- [x] T018 Initialize OHLCChart after session auth completes
- [x] T019 Connect ticker input to OHLC chart (reuse existing ticker input)
- [ ] T020 Sync resolution changes with existing timeseries chart (optional)

## Phase 6: Verification

- [ ] T021 Manual test: Load dashboard, verify OHLC chart displays for AAPL
- [ ] T022 Manual test: Switch resolutions, verify data refetches
- [ ] T023 Manual test: Refresh page, verify resolution persists
- [ ] T024 Manual test: Test invalid ticker, verify error state
- [ ] T025 Run npm run build/validate (if applicable) to ensure no syntax errors

## Dependencies

- T001-T002 must complete before T010-T016
- T003-T006 must complete before T017
- T007-T009 can run in parallel with T010-T016
- T017-T020 depends on T003-T016

## Reference Files

- Backend endpoint: src/lambdas/dashboard/ohlc.py
- Next.js implementation: frontend/src/components/charts/price-sentiment-chart.tsx
- Existing timeseries: src/dashboard/timeseries.js
- Session auth: src/dashboard/app.js (sessionUserId)
