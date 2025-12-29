# Feature 1094: Fix Irregular Candlestick Widths with Category Scale

**Feature Branch**: `002-1094-ohlc-category-scale`
**Created**: 2025-12-29
**Status**: Implementing

## Problem Statement

The OHLC Price Chart displays candlesticks with irregular widths on 1m, 5m, and 1h resolutions. Some bars are very thin (1-2px) while others are normal width. This makes the chart difficult to read and unprofessional.

**Root Cause**: Chart.js `type: 'time'` scale spaces data points proportionally to actual timestamps. Market hour gaps (overnight: 16:00-09:30 = 17.5 hours vs intraday: 1-5 minutes) cause wildly varying pixel spacing between candlesticks.

**Standard Practice**: Professional financial charts (TradingView, Bloomberg) use category/index-based spacing where each candlestick gets equal width regardless of time gaps.

## User Story 1 - Uniform Candlestick Display (Priority: P1)

User views the OHLC chart on any resolution and sees candlesticks with consistent, uniform widths.

**Acceptance Scenarios**:

1. **Given** OHLC chart with any resolution (1m, 5m, 1h, 1D), **When** user views chart, **Then** all candlesticks have identical widths

## Requirements

- **FR-001**: All candlesticks MUST render with identical width regardless of time gaps
- **FR-002**: X-axis MUST display human-readable time/date labels via tick callback
- **FR-003**: Tooltips MUST still show full timestamp on hover
- **FR-004**: Sentiment overlay line MUST align correctly with candlesticks

## Technical Changes

- X-scale: Changed from `type: 'time'` to `type: 'category'` for uniform spacing
- Labels: Formatted via tick callback accessing stored candles array
- Data: Use array indices as x values instead of timestamps
- Sentiment: Align by index instead of timestamp

## Success Criteria

- **SC-001**: Visual inspection confirms uniform candlestick widths across all resolutions
- **SC-002**: X-axis labels show readable times/dates
