# Research: E2E Test Coverage Expansion (1223)

## R1: Playwright OAuth Route Interception Pattern

**Decision**: Use `page.route()` to intercept the Cognito authorize URL and redirect to the app's callback URL with synthetic parameters.

**Rationale**: Playwright's route interception runs at the network level, matching the real user experience (browser redirect → callback → session). No fake OAuth server needed. The test controls the authorization code and state, simulating both success and error scenarios.

**Pattern**:
```typescript
await page.route('**/oauth2/authorize**', async (route) => {
  const url = new URL(route.request().url());
  const state = url.searchParams.get('state');
  // Redirect to callback with mock code
  await route.fulfill({
    status: 302,
    headers: { Location: `${callbackUrl}?code=mock-auth-code&state=${state}` },
  });
});
```

**Alternatives considered**:
- Direct API call to callback endpoint: Rejected — doesn't test browser redirect flow
- Fake OAuth server (WireMock): Rejected — infrastructure overhead, not zero-cost
- Playwright auth state files: Rejected — doesn't test the OAuth flow itself

## R2: DynamoDB Magic Link Token Extraction

**Decision**: After requesting a magic link via the API, query DynamoDB directly for the token using boto3, then navigate the browser to the verification URL.

**Rationale**: Zero cost. Tests the full verification browser flow. Only the email delivery step is skipped (tracked in Issue #731 for future MailSlurp integration).

**Pattern**:
```python
# In conftest.py or helper
def get_magic_link_token(table, email):
    """Query DynamoDB for the most recent magic link token for an email."""
    response = table.query(
        IndexName='by_email',
        KeyConditionExpression='email = :email',
        FilterExpression='entity_type = :type AND used = :false',
        ExpressionAttributeValues={':email': email, ':type': 'TOKEN', ':false': False},
        ScanIndexForward=False,
        Limit=1,
    )
    items = response.get('Items', [])
    return items[0]['PK'].replace('TOKEN#', '') if items else None
```

**Alternatives considered**:
- MailSlurp email service ($15/month): Deferred — Issue #731 for future work
- Test-only API endpoint: Rejected — security risk, code debt

## R3: Cross-Browser Configuration

**Decision**: Add Firefox and WebKit (Safari) projects to `playwright.config.ts` alongside existing Chromium projects.

**Rationale**: Existing config has Mobile Chrome, Mobile Safari, Desktop Chrome. Adding Desktop Firefox and Desktop WebKit gives full engine coverage. Safari mobile is already tested (iPhone 13 project).

**Configuration addition**:
```typescript
{
  name: 'firefox',
  use: { ...devices['Desktop Firefox'] },
},
{
  name: 'webkit',
  use: { ...devices['Desktop Safari'] },
},
```

**Alternatives considered**:
- Run all tests on all browsers: Rejected — too slow for CI, diminishing returns
- Run only sanity tests cross-browser: Accepted — new auth/session tests only on Chromium, sanity suite on all 3 engines

## R4: Test Data Isolation Strategy

**Decision**: Each test run generates a unique prefix (e.g., `E2E_{timestamp}_{random}`) for all test data. TTL-based auto-expiry ensures cleanup even if tests crash.

**Rationale**: Constitution requires synthetic test data with unique identifiers. TTL-based cleanup is already used in the existing E2E test infrastructure (test_cleanup.py).

**Pattern**:
- User IDs: `E2E_{run_id}_user_{n}`
- Config names: `E2E_{run_id}_config_{n}`
- Alert names: `E2E_{run_id}_alert_{n}`
- TTL: 24 hours from creation (auto-cleanup via DynamoDB TTL)
