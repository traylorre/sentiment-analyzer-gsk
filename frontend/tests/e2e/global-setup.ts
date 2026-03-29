// Target: Customer Dashboard (Next.js/Amplify)
// Feature 1247: Global setup — clean stale e2e- test data from previous runs

import { type FullConfig } from '@playwright/test';

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function cleanupStaleTestData() {
  try {
    // Create an anonymous session to get a token for cleanup
    const authResponse = await fetch(`${API_URL}/api/v2/auth/anonymous`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });

    if (!authResponse.ok) {
      console.log('[global-setup] Could not create session for cleanup — skipping');
      return;
    }

    const { token } = await authResponse.json();
    const headers = {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    };

    // List configurations and delete any with e2e- prefix
    const configsResponse = await fetch(`${API_URL}/api/v2/configurations`, { headers });
    if (configsResponse.ok) {
      const data = await configsResponse.json();
      const configs = data.configurations || [];
      const stale = configs.filter(
        (c: { name: string }) => c.name?.startsWith('e2e-')
      );
      for (const config of stale) {
        await fetch(`${API_URL}/api/v2/configurations/${config.config_id}`, {
          method: 'DELETE',
          headers,
        });
      }
      if (stale.length > 0) {
        console.log(`[global-setup] Cleaned up ${stale.length} stale e2e- configurations`);
      }
    }
  } catch (error) {
    // Non-fatal — cleanup is best-effort.
    // TypeError: fetch failed = API server not reachable yet (expected during startup)
    const message = error instanceof TypeError
      ? 'API not reachable yet (server may still be starting)'
      : String(error);
    console.log(`[global-setup] Cleanup skipped: ${message}`);
  }
}

export default async function globalSetup(_config: FullConfig) {
  await cleanupStaleTestData();
}
