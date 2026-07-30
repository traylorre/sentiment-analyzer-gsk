// Target: Customer Dashboard (Next.js/Amplify)
// DO NOT MERGE - 002 T018 red-team planted violation.
import { test } from '@playwright/test';

test('planted act-then-wait race', async ({ page }) => {
  const searchInput = page.getByRole('textbox', { name: 'Search tickers' });
  await searchInput.fill('AAPL');
  await page.waitForResponse('**/api/v2/tickers/search**');
});
