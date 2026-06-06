# AR#3: Final Task Review

## Consistency Check

### Spec -> Plan -> Tasks Alignment

| Spec Requirement | Plan Section | Task(s) | Status |
|-----------------|-------------|---------|--------|
| 4 tests pass with 0 sentiment | All 4 tests listed | Tasks 1-9 cover all 4 tests | ALIGNED |
| No other tests modified | Files NOT Modified table | Only sanity.spec.ts | ALIGNED |
| sentiment-visibility unchanged | Explicit exclusion | Not touched | ALIGNED |
| Works with non-zero sentiment too | Regex `[1-9]\d*` for price still matches | Verified | ALIGNED |

### Task Completeness Audit

**Test 1 (Desktop full flow)**: Tasks 1, 2, 3 cover lines 40, 44-56, 70. COMPLETE.

**Test 2 (Mobile full flow)**: Tasks 4, 5 cover lines 228, 244. COMPLETE.

**Test 3 (GOOG price data)**: Task 6 covers line 372. Lines 376-380 (price extraction)
are KEPT — they validate the GOOG regression fix which is the purpose of this test.
COMPLETE.

**Test 4 (Sentiment toggle)**: Tasks 7, 8, 9 cover lines 530, 539-546, 556-561. Toggle
interaction (lines 548-554) is preserved. COMPLETE.

### Adversarial Challenges

**Challenge 1: "Task 2 removes priceCount assertion — is that safe?"**

Yes. The regex `[1-9]\d* price candles` on line 40 already asserts price > 0. The explicit
`expect(priceCount).toBeGreaterThan(0)` is redundant. Removing it simplifies the test
without reducing coverage.

**Challenge 2: "Task 9 removes post-toggle re-check — could toggle OFF break the chart?"**

The concern would be: after toggling sentiment off and back on, does the chart still have
sentiment data in its aria-label? This is tested by `aria-pressed` returning to `true`
(line 554). If the toggle button says it's pressed but the aria-label disagrees, that's a
frontend component bug — which would also be caught by `sentiment-visibility.spec.ts` when
run against a seeded environment. The post-toggle aria-label check is defensive redundancy.

**Challenge 3: "Are there other tests in sanity.spec.ts that might break?"**

Scanning the file for all `/sentiment/` regex matches:
- Line 40: MODIFIED (Task 1)
- Line 70: MODIFIED (Task 3)  
- Line 228: MODIFIED (Task 4)
- Line 244: MODIFIED (Task 5)
- Line 372: MODIFIED (Task 6)
- Line 530: MODIFIED (Task 7)
- Line 558: REMOVED (Task 9)

Other lines that reference sentiment but use price-only regex (NO CHANGE NEEDED):
- Lines 99, 127, 167, 265, 310, 413, 469, 489, 594, 669: Already use
  `/[1-9]\d* price candles/` (price-only). These are SAFE.

**All sentiment-asserting lines are accounted for.** No missed occurrences.

### Line Number Stability

Tasks are ordered top-to-bottom in the file. Block removals (Tasks 2, 8, 9) shift
subsequent line numbers. Implementation should proceed top-to-bottom to avoid line
number drift, or use string matching rather than line numbers.

## Verdict

**READY FOR IMPLEMENTATION.** 9 tasks, all in 1 file, fully specified with exact
before/after diffs. No gaps, no drift, no missed assertions.
