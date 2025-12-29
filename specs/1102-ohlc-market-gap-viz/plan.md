# Implementation Plan: OHLC Market Gap Visualization

**Branch**: `1102-ohlc-market-gap-viz` | **Date**: 2025-12-29 | **Spec**: [spec.md](./spec.md)

## Summary

Show market closures (weekends, holidays) as red-shaded rectangles in the OHLC chart while maintaining equal-width candlesticks. Use lightweight-charts Series Primitives API for custom drawing. Insert gap markers into the data stream to maintain continuous x-axis.

## Technical Context

**Language/Version**: TypeScript 5.x (Next.js frontend)
**Primary Dependencies**: lightweight-charts v5.0.9 (Series Primitives API)
**Storage**: N/A
**Testing**: Jest, React Testing Library
**Target Platform**: Modern browsers
**Project Type**: web (frontend-only change)
**Performance Goals**: Smooth rendering with gaps, no jank
**Constraints**: Equal-width candlesticks required

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Visual consistency | ✅ PASS | Equal-width maintained |
| Performance | ✅ PASS | Primitives are efficient |

## Project Structure

```text
frontend/
├── src/
│   ├── components/charts/
│   │   ├── price-sentiment-chart.tsx    # MODIFY: Integrate gap shader
│   │   └── primitives/
│   │       └── gap-shader-primitive.ts  # CREATE: Red rectangle renderer
│   ├── lib/
│   │   └── utils/
│   │       └── market-calendar.ts       # CREATE: Gap detection logic
│   └── types/
│       └── chart.ts                     # MODIFY: Add GapMarker type
└── tests/
    └── unit/lib/utils/
        └── market-calendar.test.ts      # CREATE: Calendar tests
```

## Implementation Approach

### Phase 1: Market Calendar Utility
1. Create `market-calendar.ts` with:
   - `isMarketOpen(date, resolution)` - check if market open
   - `fillGaps(candles)` - insert gap markers between trading days
   - US market holidays list (Christmas, Thanksgiving, etc.)

### Phase 2: Gap Shader Primitive
2. Create `gap-shader-primitive.ts`:
   - Implement `ISeriesPrimitive` interface
   - `draw(target)` - render red rectangles at gap positions
   - Calculate gap positions from data indices

### Phase 3: Data Integration
3. Modify OHLC data processing:
   - Transform candles → candles with gap markers
   - Gap markers have `isGap: true, date: "YYYY-MM-DD"`
   - X-axis formatter shows all dates including gaps

### Phase 4: Chart Integration
4. Modify `price-sentiment-chart.tsx`:
   - Attach GapShaderPrimitive to candlestick series
   - Process data through `fillGaps()` before rendering
   - Handle tooltip for gap areas

## Key Technical Details

### Series Primitives Pattern
```typescript
class GapShaderPrimitive implements ISeriesPrimitive {
  private gaps: { startIndex: number; endIndex: number }[] = [];

  paneViews() { return [new GapShaderPaneView(this)]; }

  attached(p) { this.series = p.series; }

  updateGaps(gapMarkers: GapMarker[]) {
    this.gaps = gapMarkers.map(g => ({ startIndex: g.index, endIndex: g.index }));
  }
}

class GapShaderPaneView implements IPrimitivePaneView {
  renderer(): GapShaderRenderer { return new GapShaderRenderer(this.gaps); }
}

class GapShaderRenderer implements IPrimitivePaneRenderer {
  draw(target: CanvasRenderingTarget2D) {
    const ctx = target.context;
    ctx.fillStyle = 'rgba(255, 0, 0, 0.1)';
    // Draw rectangles for each gap
  }
}
```

### Gap Detection
```typescript
function fillGaps(candles: OHLCCandle[], resolution: Resolution): (OHLCCandle | GapMarker)[] {
  const result = [];
  for (let i = 0; i < candles.length - 1; i++) {
    result.push(candles[i]);
    const gap = getDatesBetween(candles[i].date, candles[i+1].date);
    gap.forEach(date => result.push({ date, isGap: true }));
  }
  result.push(candles[candles.length - 1]);
  return result;
}
```

## Files to Modify

| File | Change | Description |
|------|--------|-------------|
| `frontend/src/lib/utils/market-calendar.ts` | CREATE | Gap detection, holiday list |
| `frontend/src/components/charts/primitives/gap-shader-primitive.ts` | CREATE | Red rectangle renderer |
| `frontend/src/types/chart.ts` | MODIFY | Add GapMarker type |
| `frontend/src/components/charts/price-sentiment-chart.tsx` | MODIFY | Integrate primitive |
| `frontend/src/hooks/use-chart-data.ts` | MODIFY | Process gaps in data |
