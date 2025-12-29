# Implementation Plan: OHLC Chart X-Axis Label Refresh

**Feature**: 1104-ohlc-xaxis-label-refresh
**Created**: 2025-12-29
**Complexity**: Low (single property addition)

## Overview

Add `textColor` property to timeScale configuration to enable x-axis label refresh during pan.

## Implementation Steps

### Step 1: Add textColor to timeScale

**File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
**Location**: timeScale configuration block (~line 216)

Add `textColor: '#a3a3a3'` to match other charts in the codebase.

### Step 2: Verify Behavior

1. Load chart with 1h resolution
2. Pan left/right
3. Verify x-axis labels update to show new time range

## Risk Assessment

- **Risk**: Very low - uses existing lightweight-charts feature
- **Rollback**: Remove textColor property
- **Dependencies**: None

## Testing

- Manual: Verify x-axis labels update during pan on all resolutions
- Visual: Compare with sentiment-chart.tsx styling
