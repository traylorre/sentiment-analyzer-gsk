# Implementation Plan: OHLC Daily Resolution Scrollable View

**Feature**: 1103-ohlc-daily-scroll
**Created**: 2025-12-29
**Complexity**: Low (single-line change)

## Overview

Change `VISIBLE_CANDLES['D']` from 0 to 40 to enable scrollable daily charts.

## Implementation Steps

### Step 1: Update VISIBLE_CANDLES Configuration

**File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
**Line**: 37
**Change**: `'D': 0` → `'D': 40`

This change causes the existing viewport logic (lines 412-418) to apply `setVisibleLogicalRange()` for daily resolution, enabling scrolling.

### Step 2: Verify Behavior

1. Load chart with daily resolution
2. Confirm initial view shows ~40 candles at right edge
3. Pan left to see older data
4. Pan right to return to recent data

## Risk Assessment

- **Risk**: Very low - uses existing, tested code path
- **Rollback**: Change value back to 0
- **Dependencies**: None

## Testing

- Manual: Verify panning works on daily chart
- Existing unit tests should pass (no API changes)
