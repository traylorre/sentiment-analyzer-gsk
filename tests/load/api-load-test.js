// k6 Load Test Script for Sentiment Analyzer API
//
// Usage:
//   k6 run --env API_URL=https://your-api-url.com tests/load/api-load-test.js
//
// Environment variables:
//   API_URL - Base URL of the API (required)
//   STAGE   - Test stage: smoke, load, stress, soak (default: load)
//
// Stages:
//   smoke  - Quick validation (1 VU, 30s)
//   load   - Normal load test (ramp to 50 VUs over 5 minutes)
//   stress - Find breaking point (ramp to 200 VUs)
//   soak   - Extended duration (50 VUs for 30 minutes)

import http from "k6/http";
import { check, group, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

// Custom metrics
const errorRate = new Rate("errors");
const authLatency = new Trend("auth_latency", true);
const configLatency = new Trend("config_latency", true);
const sentimentLatency = new Trend("sentiment_latency", true);

// Test configuration based on STAGE
const stages = {
  smoke: {
    stages: [{ duration: "30s", target: 1 }],
    thresholds: {
      http_req_duration: ["p(95)<2000"],
      errors: ["rate<0.1"],
    },
  },
  load: {
    stages: [
      { duration: "1m", target: 10 }, // Ramp up
      { duration: "3m", target: 50 }, // Stay at 50 VUs
      { duration: "1m", target: 0 }, // Ramp down
    ],
    thresholds: {
      http_req_duration: ["p(95)<1500", "p(99)<3000"],
      errors: ["rate<0.05"],
    },
  },
  stress: {
    stages: [
      { duration: "2m", target: 50 },
      { duration: "2m", target: 100 },
      { duration: "2m", target: 150 },
      { duration: "2m", target: 200 },
      { duration: "2m", target: 0 },
    ],
    thresholds: {
      http_req_duration: ["p(95)<5000"],
      errors: ["rate<0.2"],
    },
  },
  soak: {
    stages: [
      { duration: "2m", target: 50 },
      { duration: "30m", target: 50 },
      { duration: "2m", target: 0 },
    ],
    thresholds: {
      http_req_duration: ["p(95)<2000"],
      errors: ["rate<0.05"],
    },
  },
};

const stage = __ENV.STAGE || "load";
const config = stages[stage];

export const options = {
  stages: config.stages,
  thresholds: {
    ...config.thresholds,
    auth_latency: ["p(95)<1000"],
    config_latency: ["p(95)<1500"],
    sentiment_latency: ["p(95)<2000"],
  },
};

const BASE_URL = __ENV.API_URL;

if (!BASE_URL) {
  throw new Error("API_URL environment variable is required");
}

// Helper to build headers
function buildHeaders(userId = null) {
  const headers = {
    "Content-Type": "application/json",
  };
  if (userId) {
    headers["X-User-ID"] = userId;
  }
  return headers;
}

// Create anonymous session
function createSession() {
  const start = Date.now();
  const response = http.post(
    `${BASE_URL}/api/v2/auth/anonymous`,
    JSON.stringify({}),
    { headers: buildHeaders() }
  );
  authLatency.add(Date.now() - start);

  const success = check(response, {
    "auth status is 200 or 201": (r) => r.status === 200 || r.status === 201,
    "auth returns token": (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.token || body.user_id;
      } catch {
        return false;
      }
    },
  });

  errorRate.add(!success);

  if (success) {
    try {
      const body = JSON.parse(response.body);
      return body.token || body.user_id;
    } catch {
      return null;
    }
  }
  return null;
}

// Get configurations
function getConfigurations(userId) {
  const start = Date.now();
  const response = http.get(`${BASE_URL}/api/v2/configurations`, {
    headers: buildHeaders(userId),
  });
  configLatency.add(Date.now() - start);

  const success = check(response, {
    "configs status is 200": (r) => r.status === 200,
    "configs returns array or object": (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body) || typeof body === "object";
      } catch {
        return false;
      }
    },
  });

  errorRate.add(!success);
  return response;
}

// Create configuration
function createConfiguration(userId) {
  const start = Date.now();
  const payload = {
    name: `Load Test Config ${Date.now()}`,
    tickers: [{ symbol: "AAPL", weight: 1.0 }],
  };

  const response = http.post(
    `${BASE_URL}/api/v2/configurations`,
    JSON.stringify(payload),
    { headers: buildHeaders(userId) }
  );
  configLatency.add(Date.now() - start);

  const success = check(response, {
    "create config status is 200 or 201": (r) =>
      r.status === 200 || r.status === 201,
    "create config returns id": (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.config_id || body.id;
      } catch {
        return false;
      }
    },
  });

  errorRate.add(!success);

  if (success) {
    try {
      const body = JSON.parse(response.body);
      return body.config_id || body.id;
    } catch {
      return null;
    }
  }
  return null;
}

// Get sentiment data
function getSentiment(userId, configId) {
  const start = Date.now();
  const response = http.get(
    `${BASE_URL}/api/v2/configurations/${configId}/sentiment`,
    { headers: buildHeaders(userId) }
  );
  sentimentLatency.add(Date.now() - start);

  const success = check(response, {
    "sentiment status is 200 or 404": (r) =>
      r.status === 200 || r.status === 404,
  });

  errorRate.add(!success && response.status !== 404);
  return response;
}

// Delete configuration (cleanup)
function deleteConfiguration(userId, configId) {
  const response = http.del(
    `${BASE_URL}/api/v2/configurations/${configId}`,
    null,
    { headers: buildHeaders(userId) }
  );

  check(response, {
    "delete config status is 200 or 204": (r) =>
      r.status === 200 || r.status === 204,
  });

  return response;
}

// Health check
function healthCheck() {
  const response = http.get(`${BASE_URL}/health`);
  check(response, {
    "health check status is 200": (r) => r.status === 200,
  });
  return response;
}

// Main test scenario
export default function () {
  // Simulate user journey
  group("User Journey", function () {
    // 1. Health check (10% of iterations)
    if (Math.random() < 0.1) {
      group("Health Check", function () {
        healthCheck();
      });
    }

    // 2. Create session
    let userId = null;
    group("Authentication", function () {
      userId = createSession();
    });

    if (!userId) {
      console.log("Failed to create session, skipping rest of iteration");
      return;
    }

    // 3. List configurations (most common operation)
    group("List Configurations", function () {
      getConfigurations(userId);
    });

    // 4. Create and query configuration (30% of iterations)
    if (Math.random() < 0.3) {
      let configId = null;
      group("Create Configuration", function () {
        configId = createConfiguration(userId);
      });

      if (configId) {
        // Query sentiment
        group("Get Sentiment", function () {
          getSentiment(userId, configId);
        });

        // Cleanup (50% of time to simulate retained configs)
        if (Math.random() < 0.5) {
          group("Delete Configuration", function () {
            deleteConfiguration(userId, configId);
          });
        }
      }
    }

    // Think time between iterations (1-3 seconds)
    sleep(1 + Math.random() * 2);
  });
}

// Setup function - runs once before the test
export function setup() {
  console.log(`Starting ${stage} test against ${BASE_URL}`);

  // Verify API is reachable
  const response = http.get(`${BASE_URL}/health`);
  if (response.status !== 200) {
    throw new Error(`API health check failed: ${response.status}`);
  }

  console.log("API health check passed");
  return { startTime: Date.now() };
}

// Teardown function - runs once after the test
export function teardown(data) {
  const duration = (Date.now() - data.startTime) / 1000;
  console.log(`Test completed in ${duration.toFixed(2)} seconds`);
}

// Handle test summary
export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    stage: stage,
    api_url: BASE_URL,
    duration_seconds: data.state.testRunDurationMs / 1000,
    metrics: {
      http_reqs: data.metrics.http_reqs?.values?.count || 0,
      http_req_duration_p50:
        data.metrics.http_req_duration?.values?.["p(50)"] || 0,
      http_req_duration_p95:
        data.metrics.http_req_duration?.values?.["p(95)"] || 0,
      http_req_duration_p99:
        data.metrics.http_req_duration?.values?.["p(99)"] || 0,
      error_rate: data.metrics.errors?.values?.rate || 0,
      auth_latency_p95: data.metrics.auth_latency?.values?.["p(95)"] || 0,
      config_latency_p95: data.metrics.config_latency?.values?.["p(95)"] || 0,
      sentiment_latency_p95:
        data.metrics.sentiment_latency?.values?.["p(95)"] || 0,
    },
    thresholds_passed: Object.values(data.thresholds || {}).every(
      (t) => t.ok
    ),
  };

  return {
    stdout: JSON.stringify(summary, null, 2) + "\n",
    "load-test-results.json": JSON.stringify(summary, null, 2),
  };
}
