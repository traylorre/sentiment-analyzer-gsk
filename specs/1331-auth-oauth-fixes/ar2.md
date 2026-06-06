# AR#2: Drift Check

## Drift Detected: A2-A4 may not need route mocks

### Finding

During clarification (Stage 4), I re-read the verify page code and found that:

```typescript
// verify/page.tsx line 24-35
const verify = async () => {
  try {
    await verifyToken(token);
    setStatus('success');
    // ...
  } catch {
    setStatus('error');
  }
};
```

The catch block catches ANY error (including network errors from missing API) and sets
`status = 'error'`. The error state renders "Invalid or expired link" heading, which
the tests A2-A4 check for.

This means tests A2-A4 might already pass without route mocks -- the network error from
the missing API would be caught, triggering the error state UI that the tests assert.

### Impact on Plan

**Reduce scope**: Tests A2-A4 may need NO changes. Only A1 and A5/A5b definitively need
route mocks.

**Validation step**: During implementation, run tests A2-A4 first WITHOUT adding mocks.
If they pass, skip the mock addition. If they fail, add mocks.

**Possible failure mode**: The `verifyMagicLink` function in the auth store may set
`isLoading = true` and never set it back to `false` on network error, leaving the
component stuck on the loading spinner. The verify page checks
`if (status === 'loading' || isLoading)` at line 40. If `isLoading` stays true even
after `setStatus('error')`, the loading UI wins and the error heading never shows.

**Mitigation**: Check the auth store's `verifyMagicLink` implementation for proper
`finally { setLoading(false) }` pattern.

### Drift: oauth-flow test 3 (B3) also needs /urls mock

The original spec categorized oauth-flow.spec.ts line 56-70 test as purely "wrong assertion"
(Category B). But during clarification, I realized it also needs the `/urls` mock because
it starts on `/auth/signin` and clicks the Google button -- which won't exist without the
mock.

**Fix**: Reclassify test B3 as dual-issue (needs /urls mock AND assertion fix).

### Updated Test Classification

| Test | File | Mock Needed? | Assertion Fix? |
|------|------|:---:|:---:|
| A1 | magic-link.spec.ts:14 | YES (magic-link) | No |
| A2 | magic-link.spec.ts:29 | MAYBE (verify) | No |
| A3 | magic-link.spec.ts:55 | MAYBE (verify) | No |
| A4 | magic-link.spec.ts:69 | MAYBE (verify) | No |
| A5 | oauth-flow.spec.ts:13 | YES (/urls) | No |
| A5b | oauth-flow.spec.ts:39 | YES (/urls, /callback) | No |
| B1 | auth.spec.ts:237 | No | YES |
| B2 | auth.spec.ts:253 | No | YES |
| B3 | oauth-flow.spec.ts:56 | YES (/urls) | YES (role) |
| B4 | signin-interaction.spec.ts:101 | No | MAYBE (timing) |

### Verdict: PROCEED with updated plan

Add route mocks only where needed. Test A2-A4 first without mocks. The scope may be
smaller than originally estimated.
