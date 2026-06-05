# AR#1: Is Relaxing the Regex Hiding a Real Bug?

## Question

If we remove sentiment count assertions from sanity tests, what happens if sentiment
stops loading in production?

## Analysis

### Current Coverage Map

| Test File | What It Tests | Sentiment Assertion |
|-----------|--------------|---------------------|
| `sanity.spec.ts` (4 tests) | Critical user path: search -> select -> chart renders | YES (currently, the problem) |
| `sentiment-visibility.spec.ts` (3 tests) | Sentiment data presence, time range updates, multi-ticker | YES (dedicated) |

### After This Change

| Test File | What It Tests | Sentiment Assertion |
|-----------|--------------|---------------------|
| `sanity.spec.ts` (4 tests) | Critical user path: search -> select -> chart renders | NO (relaxed to price-only) |
| `sentiment-visibility.spec.ts` (3 tests) | Sentiment data presence, time range updates, multi-ticker | YES (unchanged) |

### Risk Assessment

**Scenario: Sentiment stops loading in production.**

- **Before fix**: Caught by sanity tests AND sentiment-visibility tests (redundant coverage).
- **After fix**: Caught by sentiment-visibility tests ONLY.

**Is this acceptable?** YES, for the following reasons:

1. **Single Responsibility**: Sanity tests exist to verify the critical user path works
   end-to-end. They should not be the primary sentinel for data availability of a specific
   data source.

2. **`sentiment-visibility.spec.ts` is robust**: It tests:
   - AAPL chart displays sentiment data points (line 50)
   - Chart updates on time range change without errors (line 66)
   - Multiple tickers show sentiment data (line 89)

3. **CI runs both files**: Both sanity and sentiment-visibility tests run in the same
   E2E suite. If sentiment-visibility is deleted, that's a separate governance issue, not
   a reason to duplicate assertions in sanity.

### Residual Risk

**If `sentiment-visibility.spec.ts` is deleted**: No test catches production sentiment
regression. This is a governance/process risk, not a code risk.

**Mitigation**: The `sentiment-visibility.spec.ts` file could be annotated with a comment
marking it as the canonical owner of sentiment assertions. However, this is out of scope
for this feature — it's a process concern.

## Verdict

**PROCEED.** The regex relaxation is sound. Sentiment coverage is maintained by the
dedicated test file. The sanity tests gain the correct behavior: they pass when the
critical user path works (price data loads), regardless of whether the local dev
environment has sentiment data seeded.
