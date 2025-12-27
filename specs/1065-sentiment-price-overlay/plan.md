# Implementation Plan: Sentiment-Price Overlay Chart

**Feature**: 1065-sentiment-price-overlay
**Created**: 2025-12-27
**Status**: Ready for implementation

## Technical Context

- **Frontend Framework**: Vanilla JavaScript with Chart.js
- **OHLC Chart**: `src/dashboard/ohlc.js` - Uses Chart.js bar chart simulating candlesticks
- **Sentiment Chart**: `src/dashboard/timeseries.js` - Uses Chart.js line chart
- **Unified Resolution**: `src/dashboard/unified-resolution.js` - Feature 1064, already provides resolution sync
- **API Endpoints**:
  - OHLC: `/api/v2/tickers/{ticker}/ohlc?resolution=D`
  - Sentiment: `/api/v2/timeseries/{ticker}?resolution=1h`

## Architecture Decision

**Approach**: Extend the OHLC chart to include a second dataset for sentiment overlay.

The OHLC chart already uses Chart.js which supports:
- Multiple datasets on the same chart
- Dual Y-axes (left for price, right for sentiment)
- Mixed chart types (bar for OHLC, line for sentiment)

This avoids creating a separate overlay module and leverages existing Chart.js infrastructure.

## Implementation Tasks

### Phase 1: Config Update

**T001**: Add overlay configuration to `config.js`
- Add `SENTIMENT_OVERLAY_COLOR` to CONFIG.COLORS
- Add `OVERLAY_ENABLED` boolean config

### Phase 2: OHLC Chart Extension

**T002**: Extend OHLCChart class in `ohlc.js` for dual-axis support
- Add second Y-axis (yAxisID: 'sentiment') with -1 to +1 scale
- Position price Y-axis on left (not right as currently)
- Add sentiment dataset slot to chart.data.datasets

**T003**: Add sentiment data fetching to OHLCChart
- Add `loadSentimentData()` method to fetch from timeseries endpoint
- Store sentiment data in `this.sentimentData` property
- Call loadSentimentData() in parallel with loadData()

**T004**: Add sentiment overlay rendering to chart
- Add `updateSentimentOverlay()` method to update dataset[1]
- Align sentiment data points with OHLC candles by timestamp
- Handle missing data gracefully (nulls for gaps)

**T005**: Update tooltip callback to show both OHLC and sentiment
- Extend tooltip label callback to include sentiment score
- Format: "Sentiment: +0.45" or "Sentiment: N/A"

### Phase 3: Legend and Visual Polish

**T006**: Enable legend in chart options
- Show legend with "Price" and "Sentiment" labels
- Use contrasting colors (green/red for candles, blue for sentiment)

**T007**: Add CSS styles for overlay indicators
- Style any fallback messages
- Style legend positioning

### Phase 4: Integration

**T008**: Update unified resolution callback in `app.js`
- When resolution changes, reload both OHLC and sentiment data
- Ensure both datasets update together

## File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/dashboard/config.js` | Modify | Add overlay color config |
| `src/dashboard/ohlc.js` | Modify | Add dual-axis, sentiment fetch, overlay render |
| `src/dashboard/styles.css` | Modify | Add legend styles if needed |
| `src/dashboard/app.js` | Modify | Update resolution callback |

## Data Alignment Strategy

OHLC data format:
```javascript
{ date: "2025-12-27T10:00:00Z", open: 150.0, high: 152.0, low: 149.0, close: 151.0 }
```

Sentiment data format:
```javascript
{ bucket_timestamp: "2025-12-27T10:00:00Z", avg: 0.45, count: 12, ... }
```

Alignment approach:
1. Parse both datasets by timestamp
2. Create a unified timeline from OHLC dates
3. For each OHLC candle date, find matching or nearest sentiment bucket
4. Use null for sentiment where no data exists

## Success Validation

- [ ] OHLC chart shows price candles on left Y-axis
- [ ] Sentiment line appears overlaid on right Y-axis (-1 to +1)
- [ ] Tooltip shows both OHLC values and sentiment score
- [ ] Resolution changes update both datasets
- [ ] Legend clearly labels both data series
- [ ] Blue sentiment line contrasts with green/red candles
