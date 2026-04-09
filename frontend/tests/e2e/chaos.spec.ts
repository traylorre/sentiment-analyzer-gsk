// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect } from '@playwright/test';

// Chaos tests run against the API directly since the chaos dashboard
// is an HTMX/Alpine.js page served by the backend, not the Next.js frontend.
// These tests verify the full chaos lifecycle via API calls.
//
// Requirements:
// - Chaos endpoints require authenticated (non-anonymous) JWT sessions
// - The chaos-experiments DynamoDB table must exist
// - Gate (SSM kill-switch) defaults to "disarmed" -- tests run in dry-run mode
//
// When running locally with mock DynamoDB (anonymous auth only), these tests
// will be skipped automatically. They run against preprod/deployed environments
// where JWT auth and the chaos table are available.

const API_BASE = process.env.PREPROD_API_URL || 'http://localhost:8000';

// Helper: get auth token
// In preprod, this returns a JWT from the auth service.
// Locally, this returns a UUID (anonymous token) which chaos endpoints reject.
async function getAuthToken(request: any): Promise<string> {
  const response = await request.post(`${API_BASE}/api/v2/auth/anonymous`, {
    data: {},
  });
  const data = await response.json();
  return data.token;
}

// Helper: check if chaos API is available and authenticated
// Returns true only when chaos endpoints accept our token (JWT auth + table exists)
async function isChaosAvailable(request: any, token: string): Promise<boolean> {
  const resp = await request.get(`${API_BASE}/chaos/experiments`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const status = resp.status();
  // 401 = anonymous token rejected (needs JWT), 500+ = table/infra missing
  return status === 200;
}

// Helper: create and return experiment
async function createExperiment(
  request: any,
  token: string,
  scenario: string,
  params: Record<string, any> = {}
) {
  const response = await request.post(`${API_BASE}/chaos/experiments`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      scenario_type: scenario,
      duration_seconds: 60,
      blast_radius: 100,
      parameters: params,
    },
  });
  expect(response.status()).toBe(201);
  return await response.json();
}

test.describe('Chaos Injection System', () => {
  let token: string;
  let chaosAvailable = false;

  test.beforeAll(async ({ request }) => {
    try {
      token = await getAuthToken(request);
      chaosAvailable = await isChaosAvailable(request, token);
    } catch {
      // Network error, API down, or auth service unavailable.
      // Set false so 12 tests skip gracefully via test.skip(!chaosAvailable, ...)
      // instead of reporting as errors in CI.
      chaosAvailable = false;
    }
  });

  test.describe('Experiment Lifecycle (Dry-Run Mode)', () => {
    // These tests run with gate "disarmed" (default)
    // Full lifecycle works but no infrastructure changes

    test('should create experiment for each scenario type', async ({ request }) => {
      test.skip(!chaosAvailable, 'Chaos API not available (needs JWT auth + chaos-experiments DynamoDB table)');

      const scenarios = [
        'ingestion_failure',
        'dynamodb_throttle',
        'lambda_cold_start',
        'trigger_failure',
        'api_timeout',
      ];

      for (const scenario of scenarios) {
        const exp = await createExperiment(request, token, scenario);
        expect(exp.scenario_type).toBe(scenario);
        expect(exp.status).toBe('pending');
        expect(exp.experiment_id).toBeTruthy();

        // Cleanup
        await request.delete(`${API_BASE}/chaos/experiments/${exp.experiment_id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
      }
    });

    test('should start experiment in dry-run when gate is disarmed', async ({ request }) => {
      test.skip(!chaosAvailable, 'Chaos API not available (needs JWT auth + chaos-experiments DynamoDB table)');

      const exp = await createExperiment(request, token, 'ingestion_failure');

      const startResp = await request.post(
        `${API_BASE}/chaos/experiments/${exp.experiment_id}/start`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      expect(startResp.status()).toBe(200);

      const started = await startResp.json();
      expect(started.status).toBe('running');
      expect(started.results.dry_run).toBe(true);
      expect(started.results.gate_state).toBe('disarmed');
      expect(started.results.baseline).toBeTruthy();
      expect(started.results.baseline.dependencies).toBeTruthy();

      // Cleanup
      await request.post(
        `${API_BASE}/chaos/experiments/${exp.experiment_id}/stop`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      await request.delete(`${API_BASE}/chaos/experiments/${exp.experiment_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    });

    test('should stop experiment and generate post-chaos health comparison', async ({ request }) => {
      test.skip(!chaosAvailable, 'Chaos API not available (needs JWT auth + chaos-experiments DynamoDB table)');

      const exp = await createExperiment(request, token, 'lambda_cold_start', { delay_ms: 3000 });

      // Start
      await request.post(
        `${API_BASE}/chaos/experiments/${exp.experiment_id}/start`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // Stop
      const stopResp = await request.post(
        `${API_BASE}/chaos/experiments/${exp.experiment_id}/stop`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      expect(stopResp.status()).toBe(200);

      const stopped = await stopResp.json();
      expect(stopped.status).toBe('stopped');
      expect(stopped.results.stopped_at).toBeTruthy();
      expect(stopped.results.post_chaos_health).toBeTruthy();

      // Cleanup
      await request.delete(`${API_BASE}/chaos/experiments/${exp.experiment_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    });

    test('should generate experiment report with DRY_RUN_CLEAN verdict', async ({ request }) => {
      test.skip(!chaosAvailable, 'Chaos API not available (needs JWT auth + chaos-experiments DynamoDB table)');

      const exp = await createExperiment(request, token, 'dynamodb_throttle');

      // Start + Stop
      await request.post(
        `${API_BASE}/chaos/experiments/${exp.experiment_id}/start`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      await request.post(
        `${API_BASE}/chaos/experiments/${exp.experiment_id}/stop`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // Get report
      const reportResp = await request.get(
        `${API_BASE}/chaos/experiments/${exp.experiment_id}/report`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      expect(reportResp.status()).toBe(200);

      const report = await reportResp.json();
      expect(report.verdict).toBe('DRY_RUN_CLEAN');
      expect(report.dry_run).toBe(true);
      expect(report.scenario).toBe('dynamodb_throttle');
      expect(report.baseline).toBeTruthy();

      // Cleanup
      await request.delete(`${API_BASE}/chaos/experiments/${exp.experiment_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    });

    test('should list experiments with filtering', async ({ request }) => {
      test.skip(!chaosAvailable, 'Chaos API not available (needs JWT auth + chaos-experiments DynamoDB table)');

      // Create two experiments
      const exp1 = await createExperiment(request, token, 'ingestion_failure');
      const exp2 = await createExperiment(request, token, 'lambda_cold_start');

      const listResp = await request.get(`${API_BASE}/chaos/experiments`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(listResp.status()).toBe(200);

      const list = await listResp.json();
      expect(list.experiments.length).toBeGreaterThanOrEqual(2);

      // Cleanup
      await request.delete(`${API_BASE}/chaos/experiments/${exp1.experiment_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      await request.delete(`${API_BASE}/chaos/experiments/${exp2.experiment_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    });

    test('should delete experiment', async ({ request }) => {
      test.skip(!chaosAvailable, 'Chaos API not available (needs JWT auth + chaos-experiments DynamoDB table)');

      const exp = await createExperiment(request, token, 'trigger_failure');

      const deleteResp = await request.delete(
        `${API_BASE}/chaos/experiments/${exp.experiment_id}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      expect(deleteResp.status()).toBe(200);

      // Verify deleted
      const getResp = await request.get(
        `${API_BASE}/chaos/experiments/${exp.experiment_id}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      expect(getResp.status()).toBe(404);
    });
  });

  test.describe('Baseline Health Detection', () => {
    test('should capture dependency health in baseline', async ({ request }) => {
      test.skip(!chaosAvailable, 'Chaos API not available (needs JWT auth + chaos-experiments DynamoDB table)');

      const exp = await createExperiment(request, token, 'ingestion_failure');

      const startResp = await request.post(
        `${API_BASE}/chaos/experiments/${exp.experiment_id}/start`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const started = await startResp.json();

      const baseline = started.results.baseline;
      expect(baseline.captured_at).toBeTruthy();
      expect(baseline.dependencies).toBeTruthy();
      // Should check at least these services
      expect(baseline.dependencies).toHaveProperty('dynamodb');
      expect(baseline.dependencies).toHaveProperty('ssm');
      expect(baseline.dependencies).toHaveProperty('cloudwatch');
      expect(baseline.dependencies).toHaveProperty('lambda');

      // Each should have a status
      for (const [, dep] of Object.entries(baseline.dependencies) as [string, any][]) {
        expect(['healthy', 'degraded']).toContain(dep.status);
      }

      // Cleanup
      await request.post(
        `${API_BASE}/chaos/experiments/${exp.experiment_id}/stop`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      await request.delete(`${API_BASE}/chaos/experiments/${exp.experiment_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    });
  });

  test.describe('Safety Guards', () => {
    test('should reject invalid scenario type', async ({ request }) => {
      test.skip(!chaosAvailable, 'Chaos API not available (needs JWT auth + chaos-experiments DynamoDB table)');

      const resp = await request.post(`${API_BASE}/chaos/experiments`, {
        headers: { Authorization: `Bearer ${token}` },
        data: {
          scenario_type: 'drop_database',
          duration_seconds: 60,
          blast_radius: 100,
        },
      });
      expect(resp.status()).toBe(400);
    });

    test('should reject duration outside bounds', async ({ request }) => {
      test.skip(!chaosAvailable, 'Chaos API not available (needs JWT auth + chaos-experiments DynamoDB table)');

      const resp = await request.post(`${API_BASE}/chaos/experiments`, {
        headers: { Authorization: `Bearer ${token}` },
        data: {
          scenario_type: 'ingestion_failure',
          duration_seconds: 9999,
          blast_radius: 100,
        },
      });
      expect(resp.status()).toBe(400);
    });

    test('should reject blast radius outside bounds', async ({ request }) => {
      test.skip(!chaosAvailable, 'Chaos API not available (needs JWT auth + chaos-experiments DynamoDB table)');

      const resp = await request.post(`${API_BASE}/chaos/experiments`, {
        headers: { Authorization: `Bearer ${token}` },
        data: {
          scenario_type: 'ingestion_failure',
          duration_seconds: 60,
          blast_radius: 0,
        },
      });
      expect(resp.status()).toBe(400);
    });

    test('should require authentication', async ({ request }) => {
      // This test works even locally -- it verifies unauthenticated requests are rejected
      const resp = await request.post(`${API_BASE}/chaos/experiments`, {
        data: {
          scenario_type: 'ingestion_failure',
          duration_seconds: 60,
          blast_radius: 100,
        },
      });
      expect(resp.status()).toBe(401);
    });

    test('should not start already-running experiment', async ({ request }) => {
      test.skip(!chaosAvailable, 'Chaos API not available (needs JWT auth + chaos-experiments DynamoDB table)');

      const exp = await createExperiment(request, token, 'ingestion_failure');

      // Start once
      await request.post(
        `${API_BASE}/chaos/experiments/${exp.experiment_id}/start`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // Try to start again
      const resp = await request.post(
        `${API_BASE}/chaos/experiments/${exp.experiment_id}/start`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      expect(resp.status()).toBe(400);

      // Cleanup
      await request.post(
        `${API_BASE}/chaos/experiments/${exp.experiment_id}/stop`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      await request.delete(`${API_BASE}/chaos/experiments/${exp.experiment_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    });
  });

  test.describe('All Five Scenarios', () => {
    // Verify each of the 5 scenarios can go through full lifecycle

    const scenarios = [
      { type: 'ingestion_failure', params: {} },
      { type: 'dynamodb_throttle', params: { delay_ms: 500 } },
      { type: 'lambda_cold_start', params: { delay_ms: 3000 } },
      { type: 'trigger_failure', params: {} },
      { type: 'api_timeout', params: { timeout: 1 } },
    ];

    for (const { type, params } of scenarios) {
      test(`should complete full lifecycle for ${type}`, async ({ request }) => {
        test.skip(!chaosAvailable, 'Chaos API not available (needs JWT auth + chaos-experiments DynamoDB table)');

        // Create
        const exp = await createExperiment(request, token, type, params);
        expect(exp.status).toBe('pending');

        // Start (dry-run)
        const startResp = await request.post(
          `${API_BASE}/chaos/experiments/${exp.experiment_id}/start`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        expect(startResp.status()).toBe(200);
        const started = await startResp.json();
        expect(started.status).toBe('running');
        expect(started.results.dry_run).toBe(true);

        // Stop
        const stopResp = await request.post(
          `${API_BASE}/chaos/experiments/${exp.experiment_id}/stop`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        expect(stopResp.status()).toBe(200);

        // Report
        const reportResp = await request.get(
          `${API_BASE}/chaos/experiments/${exp.experiment_id}/report`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        expect(reportResp.status()).toBe(200);
        const report = await reportResp.json();
        expect(report.verdict).toBe('DRY_RUN_CLEAN');
        expect(report.scenario).toBe(type);

        // Delete
        await request.delete(`${API_BASE}/chaos/experiments/${exp.experiment_id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
      });
    }
  });
});
