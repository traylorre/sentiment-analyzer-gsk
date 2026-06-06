# Feature 1318: Fix Zoom-Out Blank Space Bug

## Status: SPECIFIED

## Problem Statement

When a user zooms out (mouse wheel) on the price-sentiment chart, the existing data points
shrink along the x-axis and blank space appears on both sides. No new data is fetched
because the zoom gesture only affects the lightweight-charts viewport -- it does not update
the React `timeRange` state that drives data fetching via `useChartData`.

**Root cause**: `handleScale: interactive` (line 201 in `price-sentiment-chart.tsx`) enables
free zoom on the time axis, but `useChartData` only refetches when `timeRange` state changes
via button clicks. No bridge exists between chart viewport changes and React data fetching.

## User Stories

1. **As a user** zooming out on the price chart with mouse wheel, I expect the chart to
   automatically load a wider time range so I see more data, not empty space.

2. **As a user** who has zoomed out and triggered an auto-upgrade, I expect the time range
   button (1W/1M/3M/6M/1Y) to reflect the new active range.

3. **As a user** on the maximum time range (1Y), I expect zooming out to NOT cause errors
   or infinite refetch loops -- it should simply stop at the 1Y boundary.

4. **As a user** zooming in, I expect no automatic time range downgrade -- I am deliberately
   focusing on a subset of the current data.

## Scope

### In Scope

- Auto-upgrade `timeRange` when the visible range extends >30% past loaded data bounds
- Debounced subscription to `subscribeVisibleLogicalRangeChange`
- Ref-based access pattern for callback to read fresh `timeRange` and `priceData.length`
- Time range button UI reflects auto-upgraded range
- Loading guard: suppress upgrade while data is in-flight
- Cleanup: unsubscribe on component unmount
- `fitContent()` loop prevention
- Unit tests for utility functions
- Existing E2E test in `chart-zoom-data.spec.ts` ("mouse-wheel zoom-out past data bounds
  auto-upgrades time range") validates end-to-end behavior

### Out of Scope

- Zoom-in auto-downgrade (user expects to keep current data when focusing)
- Custom date picker / arbitrary date range input
- Pan-only behavior (horizontal scroll without zoom)
- Intraday resolution auto-switching on zoom (separate feature)
- Touch pinch-zoom on mobile (separate UX consideration)

## Requirements

### R1: Time Range Upgrade Utilities

Add to `frontend/src/types/chart.ts`:

```typescript
/** Ordered list of time ranges from narrowest to widest */
export const TIME_RANGE_ORDER: TimeRange[] = ['1W', '1M', '3M', '6M', '1Y'];

/**
 * Get the next wider time range, or null if already at maximum.
 */
export function getNextTimeRange(current: TimeRange): TimeRange | null;

/**
 * Determine if the visible logical range extends far enough past loaded data
 * to warrant an upgrade. Returns true when the visible range exceeds the
 * loaded data extent by more than 30%.
 *
 * @param visibleFrom - Left edge of visible range (bar index, can be negative)
 * @param visibleTo - Right edge of visible range (bar index)
 * @param dataLength - Number of data points currently loaded
 */
export function shouldUpgradeTimeRange(
  visibleFrom: number,
  visibleTo: number,
  dataLength: number,
): boolean;
```

### R2: Viewport Change Subscription

In the chart initialization `useEffect` (lines 172-357 of `price-sentiment-chart.tsx`),
after chart creation and when `interactive` is true:

1. Subscribe to `chart.timeScale().subscribeVisibleLogicalRangeChange(callback)`.
2. The callback reads `dataLengthRef.current` and `timeRangeRef.current` via refs (NOT
   via closure over state, which would capture stale values since the subscription is
   created once).
3. If `shouldUpgradeTimeRange(range.from, range.to, dataLength)` returns true AND the
   current time range is not already at '1Y', call `setTimeRange(nextRange)`.
4. Store the unsubscribe function and call it in the cleanup return.

### R3: Debounce (500ms)

The `subscribeVisibleLogicalRangeChange` callback fires on every frame during wheel zoom.
Wrap the upgrade check in a 500ms debounce:

- Use a `setTimeout` / `clearTimeout` pattern stored in a ref.
- Clear the timeout in the cleanup function to prevent post-unmount execution.

### R4: Loading Guard

Suppress time range upgrades while data is loading (`isLoading === true`):

- Store `isLoading` in a ref (`isLoadingRef`).
- Check `isLoadingRef.current` inside the debounced callback. If loading, skip the upgrade.
- This prevents: user zooms out -> upgrade to 3M starts loading -> `fitContent()` fires
  on the partial data -> visible range still extends past bounds -> another upgrade to 6M.

### R5: fitContent Loop Prevention

After new data loads (in the `priceData` useEffect at line 360), `fitContent()` is called.
This resets the visible range to fit all data, which fires
`subscribeVisibleLogicalRangeChange`. The callback must NOT trigger another upgrade because:

- After `fitContent()`, the visible range matches the loaded data exactly.
- `shouldUpgradeTimeRange` returns false when `visibleFrom >= 0` and
  `visibleTo <= dataLength` (i.e., no overshoot).
- **Additional safeguard**: Set a `justFitContentRef` flag to `true` before calling
  `fitContent()`, and check it in the subscription callback. Reset to `false` after a
  short delay (100ms) or on the next callback invocation.

### R6: Maximum Range Cap

When `timeRange` is already '1Y', `getNextTimeRange` returns `null`. The callback must
check for `null` and skip the upgrade. No error, no loop, no console warning.

### R7: Ref Synchronization

Add refs that mirror React state for access inside the one-time subscription callback:

```typescript
const dataLengthRef = useRef(0);
const timeRangeRef = useRef<TimeRange>(timeRange);
const isLoadingRef = useRef(isLoading);
```

Update these refs in the respective `useEffect` hooks or directly in the render body
(before the return statement) to keep them in sync.

### R8: Cleanup

The subscription callback's debounce timeout must be cleared on unmount:

```typescript
return () => {
  clearTimeout(debounceTimerRef.current);
  // ... existing cleanup
};
```

### R9: Non-Interactive Mode

When `interactive === false`, `handleScale` is already `false` (line 201), so the user
cannot zoom. The subscription should NOT be created when `interactive` is false. This is
naturally handled because the subscription is inside the `if (interactive)` block.

## Edge Cases

### EC1: Already at 1Y Maximum
- `getNextTimeRange('1Y')` returns `null`.
- Callback sees `null`, does nothing. User sees blank space but no crash or loop.
- Acceptable UX: 1Y is the maximum data the API provides.

### EC2: Rapid Successive Zooms
- Each wheel event fires `subscribeVisibleLogicalRangeChange`.
- The 500ms debounce collapses all events in a burst into a single upgrade check.
- Only one `setTimeRange` call fires per burst.

### EC3: Data Loading During Zoom
- `isLoadingRef.current === true` -> upgrade suppressed.
- When loading completes, `fitContent()` resets viewport to fit new data.
- If user is still zooming out, the next debounce cycle will check again.

### EC4: Empty Data Set
- `dataLength === 0` -> `shouldUpgradeTimeRange` should return `false` (nothing to
  compare against). Guard: `if (dataLength === 0) return false;`.

### EC5: Zoom-In (Narrowing Viewport)
- `visibleFrom >= 0` and `visibleTo <= dataLength` -> `shouldUpgradeTimeRange` returns
  `false`. No upgrade triggered. Correct behavior.

### EC6: Component Unmount During Debounce
- `clearTimeout` in cleanup prevents the callback from firing after unmount.
- Even if it somehow fires (race condition), `setTimeRange` on an unmounted component
  is a no-op in React 18+ (no state update on unmounted).

### EC7: Session Storage Persistence
- When auto-upgrade changes `timeRange`, the existing `useEffect` (lines 147-152) writes
  the new range to `sessionStorage`. Next page load will start with the wider range. This
  is correct behavior -- the user's last-used range should persist.

### EC8: Multiple Upgrades in Sequence
- User zooms out past 1M -> upgrade to 3M -> data loads -> fitContent -> user zooms out
  again past 3M -> upgrade to 6M. Each step is independent and correct. The loading guard
  prevents overlap.

## Success Criteria

1. **SC1**: Mouse-wheel zoom-out past loaded data bounds triggers automatic time range
   upgrade within 1 second (500ms debounce + state update + refetch).

2. **SC2**: Time range button UI highlights the auto-upgraded range (e.g., 3M button
   becomes active after upgrade from 1M).

3. **SC3**: No infinite loops: fitContent after data load does NOT trigger another upgrade.

4. **SC4**: At 1Y maximum, zoom-out produces blank space but no errors, no console
   warnings, no refetch attempts.

5. **SC5**: Zoom-in does NOT trigger any time range changes.

6. **SC6**: E2E test `chart-zoom-data.spec.ts` "mouse-wheel zoom-out past data bounds
   auto-upgrades time range" passes.

7. **SC7**: No memory leaks: subscription and debounce timer cleaned up on unmount.

8. **SC8**: Existing E2E tests for chart data visibility continue to pass (no regression).

## Files to Modify

| File | Change |
|------|--------|
| `frontend/src/types/chart.ts` | Add `TIME_RANGE_ORDER`, `getNextTimeRange()`, `shouldUpgradeTimeRange()` |
| `frontend/src/components/charts/price-sentiment-chart.tsx` | Add refs, subscription, debounce, loading guard, fitContent flag |
| `frontend/tests/unit/types/chart-utils.test.ts` (new) | Unit tests for `getNextTimeRange` and `shouldUpgradeTimeRange` |

## Sibling Analysis

Only `price-sentiment-chart.tsx` is affected:
- `atr-chart.tsx`, `sentiment-chart.tsx` - receive data from parent props, no independent
  zoom-to-fetch behavior needed.
- `use-chart-sync.ts` - uses `subscribeVisibleTimeRangeChange` (not logical range), no
  conflict. The two subscriptions coexist on the same chart instance without interference.

## Prior Art

- `use-chart-sync.ts` lines 142-148: demonstrates `subscribeVisibleTimeRangeChange`
  subscription pattern within a hook.
- Feature 1316: `fitContent()` timing fix -- established the pattern of calling fitContent
  inline after `setData()` in the same `useEffect`.

---

## Adversarial Review #1

### Attack Surface Analysis

| ID | Severity | Finding | Attack Vector | Resolution |
|----|----------|---------|---------------|------------|
| AR1-001 | CRITICAL | **fitContent -> subscribeVisibleLogicalRangeChange loop**: After data loads, `fitContent()` is called (line 400). This adjusts the visible range, which fires the subscription callback. If the new data fits exactly, `shouldUpgradeTimeRange` returns false (correct). But if `fitContent()` leaves any negative `from` index (e.g., chart padding/margins), it could trigger a false positive upgrade. | `fitContent()` with chart margins set to `{ top: 0.1, bottom: 0.1 }` on both scales. Time scale has no explicit margins, but lightweight-charts may add implicit padding. | **RESOLVED in R5**: Added `justFitContentRef` flag. Set to `true` before `fitContent()`, checked in callback, reset after 100ms. This is a belt-and-suspenders defense alongside the threshold math. Additionally, the 30% threshold is generous enough that lightweight-charts' internal padding (typically 2-5% of range) will not trigger it. |
| AR1-002 | CRITICAL | **Debounce timeout fires after unmount**: `setTimeout` callback executes after component unmounts, calling `setTimeRange` on unmounted component. | Fast navigation away from chart while zoom debounce is pending. | **RESOLVED in R8**: `clearTimeout(debounceTimerRef.current)` in the useEffect cleanup. React 18+ also silently ignores state updates on unmounted components, but cleanup is the proper defense. |
| AR1-003 | HIGH | **Loading guard race**: Data finishes loading, `isLoadingRef` updates to `false`, but `fitContent()` hasn't fired yet. In the gap between loading-complete and fitContent-complete, the subscription could fire from the old viewport (which still extends past bounds) and trigger another upgrade. | Fast data fetch where React batches the loading state update and data update in the same commit, but the subscription callback runs between `setData()` and `fitContent()`. | **RESOLVED**: `fitContent()` is called synchronously after `setData()` in the same `useEffect` (Feature 1316 pattern, line 399-401). There is no gap between data set and fit. The subscription callback will see the already-fitted range. Combined with the `justFitContentRef` flag, this is double-protected. |
| AR1-004 | HIGH | **30% threshold analysis**: Is 30% too aggressive or too conservative? Too aggressive: upgrades on minor zoom-out, user didn't want more data. Too conservative: user sees blank space for too long before upgrade triggers. | User zooms out gently (1-2 wheel ticks). | **RESOLVED**: 30% means the visible range must extend 30% beyond loaded data on either side. With ~22 candles (1M daily), this requires ~6.6 extra bars of blank space visible, which corresponds to ~3-4 deliberate wheel zoom-out ticks. This is a reasonable "intentional zoom-out" threshold. Too-aggressive risk is low because casual scrolling rarely exceeds 10-15% overshoot. |
| AR1-005 | HIGH | **Debounce timing vs data load time**: 500ms debounce fires, triggers upgrade, data takes 2s to load. During that 2s, the loading guard blocks further upgrades. But what if the user stops zooming during the 2s load, then resumes zooming after data arrives? | User zooms -> waits -> zooms again. | **RESOLVED**: This is the correct behavior. After data loads, `fitContent()` resets the viewport. If the user zooms out again, a new debounce cycle starts. Each zoom-load-fit cycle is independent. No issue here. |
| AR1-006 | MEDIUM | **subscribeVisibleLogicalRangeChange vs subscribeVisibleTimeRangeChange**: Which API to use? `use-chart-sync.ts` uses `subscribeVisibleTimeRangeChange` (returns Time values). The spec calls for `subscribeVisibleLogicalRangeChange` (returns bar indices). | Choosing the wrong API would either give unusable data or conflict with existing sync. | **RESOLVED**: `subscribeVisibleLogicalRangeChange` is correct. It returns `{ from: number, to: number }` as bar indices (0-based). This makes the threshold calculation trivial: `from < 0` means blank space on the left, `to > dataLength` means blank space on the right. The Time-based API would require date arithmetic which is fragile with gaps/holidays. No conflict with the existing sync subscription -- both can coexist on the same chart. |
| AR1-007 | MEDIUM | **`interactive=false` bypass**: What if a consumer sets `interactive=true` but `handleScale=false` separately? | Prop misconfiguration. | **RESOLVED**: The component only exposes `interactive` prop. `handleScale` is derived directly from `interactive` on line 201. No way for a consumer to set them independently. Non-issue in current API. |
| AR1-008 | MEDIUM | **Session storage side effect**: Auto-upgrade writes to sessionStorage (via existing useEffect on line 147). If user prefers 1M but accidentally zooms out, their preference is overwritten to 3M. | Accidental zoom gesture. | **ACCEPTED**: This matches the existing button-click behavior -- clicking 3M also persists to sessionStorage. The 30% threshold + 500ms debounce means accidental upgrades require deliberate zoom effort. If this becomes a UX concern, it can be addressed separately with an "auto-upgraded" indicator and undo button. Not in scope for this bug fix. |
| AR1-009 | LOW | **Memory leak: subscription not cleaned up**: If `subscribeVisibleLogicalRangeChange` returns an unsubscribe function that is not called on cleanup. | Component remount due to key change or route navigation. | **RESOLVED in R2/R8**: The spec explicitly requires storing the unsubscribe function and calling it in the cleanup return of the initialization `useEffect`. |
| AR1-010 | LOW | **Logical range `null` callback**: lightweight-charts can call the subscription with `null` when the chart has no data or is being destroyed. | Chart initialization before data loads. | **RESOLVED**: The callback must guard with `if (!range) return;` at the top. Added as implicit requirement in R2 (the callback checks `range.from` and `range.to`, which would throw on null without the guard). Making this explicit: the callback MUST check for null range before any property access. |

### Unresolved Findings

None. All CRITICAL and HIGH findings are resolved. MEDIUM findings are either resolved or
accepted with documented rationale. LOW findings are resolved with explicit guards.

### Gate Statement

**ADVERSARIAL REVIEW #1: PASS**

All 10 findings addressed. 8 resolved in spec requirements, 1 accepted with rationale
(AR1-008, session storage side effect), 1 confirmed as non-issue (AR1-007, interactive
prop encapsulation). No unresolved CRITICAL or HIGH findings. Spec is ready for Stage 3
(Plan).

---

## Clarifications (Stage 4)

### C1: Should zoom-in auto-downgrade the time range?

**Question**: If a user is on 3M and zooms in to see only 2 weeks of data, should the
time range downgrade to 1M or 1W?

**Self-answer: NO.** The spec explicitly excludes this (Out of Scope, User Story 4). The
reasoning is sound: when a user zooms in, they are deliberately focusing on a subset of
the loaded data. Downgrading would trigger a refetch that replaces 3M of data with 1M,
losing the context the user chose. Additionally, `shouldUpgradeTimeRange` only fires
when `visibleFrom < 0` or `visibleTo > dataLength` (overshoot past data bounds), which
never occurs when zooming in. The math naturally prevents it with no special guard
needed.

**Resolution**: Confirmed correct as specified. No change needed.

### C2: Does `fitContent()` trigger `subscribeVisibleLogicalRangeChange`?

**Question**: When `fitContent()` is called after new data loads, does it fire the visible
logical range change callback? If so, could it trigger an unwanted upgrade?

**Self-answer: YES, it fires the callback.** `fitContent()` changes the visible range to
fit all data, which triggers `subscribeVisibleLogicalRangeChange`. However, after
`fitContent()`, the visible range exactly matches the data bounds (`from ≈ 0`,
`to ≈ dataLength`), so `shouldUpgradeTimeRange` returns false (no overshoot). The spec
adds `justFitContentRef` as a belt-and-suspenders guard: set `true` before `fitContent()`,
checked in the callback, reset after 100ms.

**Verification**: Confirmed by examining all `fitContent()` call sites in the codebase
(lines 400, 429 in `price-sentiment-chart.tsx`). Both are in data-update `useEffect`
hooks that set data then immediately fit. The lightweight-charts documentation confirms
that `fitContent` adjusts the visible range, which triggers range-change subscriptions.

**Resolution**: Both defenses (math + flag) are needed. The 100ms delay on flag reset
accounts for async event loop scheduling where the subscription callback might fire on
the next microtask after `fitContent()` returns.

### C3: Should the time range button UI update immediately or after data loads?

**Question**: When auto-upgrade triggers (e.g., 1M -> 3M), should the 3M button highlight
immediately (optimistic) or only after new data arrives?

**Self-answer: IMMEDIATELY.** The `setTimeRange('3M')` call updates React state, which
causes the button bar to re-render with `timeRange === '3M'` immediately. The data fetch
happens asynchronously via React Query. The loading overlay shows while data is in
flight. This matches the existing behavior when the user clicks a time range button
directly (line 452-456: `setTimeRange(newRange)` fires, UI updates, data follows).

**Verification**: Confirmed by reading `handleTimeRangeChange` (line 451-456). It calls
`setTimeRange(newRange)` which is the same function the subscription callback calls.
The button highlight is driven by `timeRange === range` in the JSX (line 534), which
reads from React state, not from data loading state.

**Resolution**: No special handling needed. Existing UI update path handles it correctly.

### C4: What happens to session storage persistence when auto-upgrading?

**Question**: Does the auto-upgrade persist the new time range to sessionStorage? Is this
desirable?

**Self-answer: YES, it persists.** The `useEffect` on line 148-152 writes `timeRange` to
sessionStorage whenever it changes, regardless of the source of the change (button click
or auto-upgrade). This means if a user auto-upgrades from 1M to 3M, refreshing the page
will start with 3M.

**Verification**: Confirmed by reading the sessionStorage effect (line 148-152) and the
initialization logic (line 112-120). The effect fires on any `timeRange` state change.

**Resolution**: Accepted as correct behavior (per AR1-008). The user's last-used range
should persist. If this causes confusion, a future feature could add an "auto-upgraded"
visual indicator, but that is out of scope for this bug fix.

### C5: Can Feature 1101 (pan-to-load) conflict with this feature?

**Question**: Feature 1101 was specified to use `subscribeVisibleLogicalRangeChange` for
pan-to-load (infinite scroll). Would two subscribers on the same API conflict?

**Self-answer: NO CONFLICT.** Feature 1101 was specified but **not implemented** -- there
is no `subscribeVisibleLogicalRangeChange` call anywhere in the current source code
(`frontend/src/`). lightweight-charts supports multiple subscribers on the same event
(standard pub-sub pattern). If 1101 is implemented later, both callbacks would fire
independently. The pan-to-load callback would check for edge proximity, while the
zoom-out callback checks for overshoot. Their trigger conditions are distinct: panning
moves the visible window without changing its width, while zooming changes the width.
They would not interfere with each other.

**Resolution**: No conflict. Feature 1101's future implementation is a separate concern.
