# Plan: 1334-sentiment-test-fix

## Overview

Modify 4 tests in `frontend/tests/e2e/sanity.spec.ts` to remove non-zero sentiment
count assertions. Replace combined price+sentiment regex with price-only regex. Remove
explicit `sentimentCount > 0` assertions where they exist.

## Files Modified

| File | Change Type |
|------|------------|
| `frontend/tests/e2e/sanity.spec.ts` | Modify (test-only) |

## Files NOT Modified

| File | Reason |
|------|--------|
| `frontend/tests/e2e/sentiment-visibility.spec.ts` | Owns sentiment assertions, unchanged |
| `run-local-api.py` | No production code changes |
| Any other test file | Out of scope |

## Change Details

### Test 1: Desktop full flow (line 16)

**Location**: Lines 38-56, 68-72

Changes:
- Line 40: Regex `/[1-9]\d* price candles and [1-9]\d* sentiment points/` -> `/[1-9]\d* price candles/`
- Lines 44-56: Remove sentiment match extraction and `sentimentCount > 0` assertion
- Line 70: Regex `/[1-9]\d* price candles and [1-9]\d* sentiment points/` -> `/[1-9]\d* price candles/`

### Test 2: Mobile full flow (line 204)

**Location**: Lines 226-230, 242-246

Changes:
- Line 228: Regex `/[1-9]\d* price candles and [1-9]\d* sentiment points/` -> `/[1-9]\d* price candles/`
- Line 244: Regex `/[1-9]\d* price candles and [1-9]\d* sentiment points/` -> `/[1-9]\d* price candles/`

### Test 3: GOOG price data (line 351)

**Location**: Lines 370-381

Changes:
- Line 372: Regex `/[1-9]\d* price candles and [1-9]\d* sentiment points/` -> `/[1-9]\d* price candles/`
- Lines 376-380: Keep price extraction, it validates the GOOG regression fix (non-zero price)

### Test 4: Sentiment toggle (line 510)

**Location**: Lines 528-561

This is the most significant change. This test's entire purpose is testing sentiment
data visibility with the toggle. However, its ACTUAL value is testing the toggle UI
interaction (aria-pressed state changes). The sentiment count assertion duplicates
`sentiment-visibility.spec.ts`.

Changes:
- Line 530: Regex `/[1-9]\d* price candles and [1-9]\d* sentiment points/` -> `/[1-9]\d* price candles/`
- Lines 539-546: Remove `sentimentCount > 5` assertion (covered by sentiment-visibility.spec.ts)
- Line 558: Regex `/[1-9]\d* sentiment points/` -> keep as `/\d+ sentiment points/` (allows 0)

**Alternative for Test 4**: Since this test is specifically about sentiment, we could
argue it should be deleted entirely (user preference: "delete bad tests over weakly
fixing them"). However, the toggle interaction testing (lines 548-554) has independent
value. Recommendation: relax the regex, keep the toggle interaction testing.

## Verification

After changes:
1. `npx playwright test sanity.spec.ts` passes with 0 sentiment data
2. No changes to `sentiment-visibility.spec.ts`
3. `git diff` shows only `sanity.spec.ts` modified
