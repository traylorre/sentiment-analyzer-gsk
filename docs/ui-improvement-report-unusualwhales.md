# UI Improvement Report: Learning from Unusual Whales

**Date**: 2025-12-27
**Source Analysis**: unusualwhales.com
**Target**: sentiment-analyzer-gsk dashboard

## Executive Summary

Unusual Whales is a leading options flow and dark pool analytics platform used by retail traders. Their UI patterns are battle-tested for high-frequency financial data visualization. This report identifies the top 5 UI improvements that would elevate the sentiment-analyzer-gsk dashboard.

---

## Top 5 UI Improvements

### 1. Dark Mode Theme (Priority: HIGH)

**What Unusual Whales Does**:
- Uses a sophisticated dark theme with `#010b14` (very dark blue-black) background
- Dark mode is standard for trading dashboards - reduces eye strain during long sessions
- High contrast for readability of financial data

**Current State in sentiment-analyzer-gsk**:
- Light mode only (`--background-color: #f9fafb`)
- No theme toggle
- Light backgrounds can cause fatigue during extended use

**Recommended Implementation**:
```css
/* Dark mode variables */
:root.dark {
    --background-color: #0f172a;
    --card-background: #1e293b;
    --text-color: #f1f5f9;
    --text-muted: #94a3b8;
    --border-color: #334155;
}
```

**User Value**: Professional traders prefer dark mode. A theme toggle would align with industry standards.

---

### 2. Traffic Light Status Indicator System (Priority: HIGH)

**What Unusual Whales Does**:
- Three-color status indicator: RED/YELLOW/GREEN
- RED = "not all trades pushed LIVE"
- YELLOW = "most trades pushed LIVE"
- GREEN = "all trades pushed LIVE"
- Clear visual feedback on data quality/freshness

**Current State in sentiment-analyzer-gsk**:
- Binary status: connected (green pulse) or disconnected (red)
- No degraded/partial state indication
- Polling mode uses amber but no clear user education

**Recommended Implementation**:
- Add visible tooltip/legend explaining each status color
- Add timestamp showing "Last data: 3s ago" next to status indicator
- Consider adding data freshness percentage: "98% of data live"

**Files to Modify**:
- `src/dashboard/styles.css` - Already has `.status-dot.polling` amber
- `src/dashboard/index.html` - Add tooltip/legend element
- `src/dashboard/app.js` - Add data age tracking

---

### 3. Advanced Filtering UI with Tag Chips (Priority: MEDIUM)

**What Unusual Whales Does**:
- Tag-based filtering (biotech, earnings, volatility, etc.)
- "Excluded tags" toggle to remove categories
- Numeric threshold filters (premium minimums, volume ratios)
- Chips/pills UI pattern for active filters

**Current State in sentiment-analyzer-gsk**:
- Resolution selector buttons (1m, 5m, 10m, 1h, etc.)
- Ticker input field
- No tag filtering for sentiment sources
- No way to filter by sentiment score range

**Recommended Implementation**:
```html
<div class="filter-chips">
    <span class="filter-chip active">All Sources</span>
    <span class="filter-chip">News</span>
    <span class="filter-chip">Social</span>
    <span class="filter-chip">Filings</span>
</div>
<div class="filter-range">
    <label>Sentiment Range:</label>
    <input type="range" min="-1" max="1" step="0.1" />
</div>
```

**User Value**: Power users can focus on specific data subsets (e.g., only negative news, only social media sentiment).

---

### 4. Configurable Dashboard Layout (Priority: MEDIUM)

**What Unusual Whales Does**:
- "Super Dashboard" - configurable dashboard combining options flow, dark pools, short activity
- Users can arrange components per preference
- Per-ticker "dashboard-like appearance" consolidating analytics

**Current State in sentiment-analyzer-gsk**:
- Fixed layout: Metrics → Resolution → OHLC Chart → Sentiment/Tag/Timeseries → Table → Stats
- No customization options
- All users see same layout regardless of use case

**Recommended Implementation**:
- Start simple: Allow users to collapse/expand sections
- Add localStorage persistence for collapsed state
- Future: Drag-and-drop reordering of dashboard cards

```javascript
// Toggle section visibility
document.querySelectorAll('.section-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
        const section = btn.closest('section');
        section.classList.toggle('collapsed');
        localStorage.setItem(section.id + '-collapsed', section.classList.contains('collapsed'));
    });
});
```

---

### 5. Data Density Controls (Priority: LOW)

**What Unusual Whales Does**:
- Dense data tables with extensive column information
- Volume, open interest, strike price, order type all visible
- "Hottest Contracts" quick view for most popular items
- Compact mode for experienced users

**Current State in sentiment-analyzer-gsk**:
- Recent Items table shows: Time, Sentiment, Score, Title, Source, Tags
- Fixed column set
- No compact/expanded modes
- No "hottest" or "trending" quick view

**Recommended Implementation**:
- Add "Compact Mode" toggle that reduces padding and font sizes
- Add "Trending Tickers" widget showing most active symbols
- Consider column visibility toggles for power users

```css
.compact-mode table {
    font-size: 0.75rem;
}
.compact-mode th, .compact-mode td {
    padding: var(--spacing-xs);
}
```

---

## Implementation Priority Matrix

| Improvement | Effort | Impact | Priority |
|-------------|--------|--------|----------|
| Dark Mode Theme | Medium | High | 1 |
| Traffic Light Status | Low | High | 2 |
| Filter Chips UI | Medium | Medium | 3 |
| Collapsible Sections | Low | Medium | 4 |
| Data Density Controls | Low | Low | 5 |

## Quick Wins (< 1 day each)

1. **Status tooltip**: Add "Last updated: Xs ago" next to connection status
2. **Collapsible sections**: Add expand/collapse toggles with localStorage
3. **Compact mode toggle**: CSS class swap for dense data viewing

## Requires Design Spec (Feature Work)

1. **Dark mode**: Full color system redesign, theme toggle component
2. **Advanced filtering**: Filter chip components, sentiment range slider, localStorage persistence

---

## Sources

- [Unusual Whales Features](https://unusualwhales.com/features)
- [Unusual Whales Review 2025](https://optionstradingiq.com/unusual-whales-review/)
- [Flow Status Indicator Documentation](https://docs.unusualwhales.com/features/flow-status-indicator-live-options-feed/)
- [Traders List Platform Review](https://www.traderslist.io/platform-trade-analytics-orderflow-unusual-whales)
