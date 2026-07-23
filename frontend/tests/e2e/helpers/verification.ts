/**
 * Verification evidence fixture (Milestone 1, WI-1).
 * Target: Customer Dashboard (Next.js/Amplify)
 *
 * Trust contract (docs/cleanup-pristine/milestone-1-verifiable-auth.md):
 * tests emit named screenshots plus a per-spec manifest that a separate
 * verifier agent attests. Nothing here asserts features work; it records
 * evidence so an independent party can judge.
 *
 * Manifest fields per trust-contract item 3:
 * - every /api/v2/auth/* request since the previous step ({method, path, status},
 *   2xx INCLUDED, not only failures)
 * - other API responses >= 400, console errors, pageerror events
 * - page_url and main-document HTTP status at capture
 * - DOM probe result (selector presence / text)
 * - target: 'preprod' | 'localhost-mock'
 * - interception: whether ANY page.route()/context.route() handlers were
 *   registered at capture time (a mocked "preprod" run must be detectable)
 * - forbidden_requests: declared per spec, evaluated at teardown so
 *   negative-space claims ("no second anonymous session was minted") are
 *   machine-checkable, never prose.
 *
 * Usage:
 *   import { test, expect } from './helpers/verification';
 *   test('guest flow', async ({ page, verify }) => {
 *     verify.forbid({ method: 'POST', path: '/api/v2/auth/anonymous', status: 201, max_count: 1 });
 *     await page.goto('/');
 *     await verify.shot('landing', { probe: { selector: 'header' } });
 *   });
 */

import {
  test as base,
  expect,
  type Page,
  type BrowserContext,
  type TestInfo,
} from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

// ─── Types ──────────────────────────────────────────────────────────────────

export interface AuthRequestEntry {
  method: string;
  path: string;
  status: number;
}

export interface ForbiddenRequestRule {
  method: string;
  /** Substring or exact pathname to match against request pathname. */
  path: string;
  /** Only responses with this status count (omit = any status). */
  status?: number;
  /** Maximum allowed occurrences across the whole spec (0 = never). */
  max_count: number;
}

export interface ForbiddenRequestResult extends ForbiddenRequestRule {
  observed_count: number;
  pass: boolean;
}

export interface DomProbe {
  selector: string;
  /** If set, the probe also records whether this text appears in the element. */
  expect_text?: string;
}

export interface DomProbeResult {
  selector: string;
  present: boolean;
  text?: string;
  expect_text?: string;
  text_match?: boolean;
}

export interface ManifestStep {
  n: number;
  name: string;
  file: string;
  /** Informational only. Pass criteria live in WI-2's canonical table. */
  expected_ui_state?: string;
  page_url: string;
  main_status: number | null;
  auth_requests: AuthRequestEntry[];
  api_errors: AuthRequestEntry[];
  console_errors: string[];
  page_errors: string[];
  dom_probe?: DomProbeResult;
  timestamp: string;
  test_location: string;
  interception_at_capture: boolean;
}

export interface VerificationManifest {
  schema: string;
  spec: string;
  run_id: string;
  project: string;
  target: 'preprod' | 'localhost-mock';
  base_url: string;
  started_at: string;
  finished_at?: string;
  steps: ManifestStep[];
  forbidden_requests: ForbiddenRequestResult[];
  interception: { route_registrations: number; clean: boolean };
}

export interface Verify {
  /** Capture a named, numbered, full-page screenshot plus its manifest entry. */
  shot(
    name: string,
    opts?: { expected_ui_state?: string; probe?: DomProbe }
  ): Promise<void>;
  /** Declare a negative-space rule, evaluated at spec teardown. */
  forbid(rule: ForbiddenRequestRule): void;
}

// ─── Constants ──────────────────────────────────────────────────────────────

const PREPROD_URL = 'https://main.d29tlmksqcx494.amplifyapp.com';
const AUTH_PATH_PREFIX = '/api/v2/auth/';

function runId(): string {
  // CI passes VERIFICATION_RUN_ID (e.g. the workflow run id) for stable artifact
  // names; local runs get a sortable timestamp id.
  return (
    process.env.VERIFICATION_RUN_ID ??
    new Date().toISOString().replace(/[:.]/g, '-')
  );
}

// One run id per worker process; all specs in a run share it.
const RUN_ID = runId();

function specSlug(testInfo: TestInfo): string {
  return path
    .basename(testInfo.file)
    .replace(/\.spec\.(ts|tsx)$/, '')
    .replace(/[^a-zA-Z0-9-]/g, '-');
}

function frontendRoot(testInfo: TestInfo): string {
  // Anchor on the config file's directory (frontend/), NOT config.rootDir,
  // which Playwright resolves to the testDir (frontend/tests/e2e) and would
  // land evidence outside the gitignored frontend/test-results/ tree.
  return testInfo.config.configFile
    ? path.dirname(testInfo.config.configFile)
    : path.resolve(testInfo.config.rootDir, '../..');
}

function outputDir(testInfo: TestInfo): string {
  // frontend/test-results/verification/{run-id}/{project}/
  // Project-namespaced so multi-browser runs cannot collide.
  return path.join(
    frontendRoot(testInfo),
    'test-results',
    'verification',
    RUN_ID,
    testInfo.project.name
  );
}

// ─── Fixture ────────────────────────────────────────────────────────────────

export const test = base.extend<{ verify: Verify }>({
  verify: async ({ page, context }, use, testInfo) => {
    const slug = specSlug(testInfo);
    const dir = outputDir(testInfo);
    fs.mkdirSync(dir, { recursive: true });

    const target: VerificationManifest['target'] =
      (process.env.PREPROD_FRONTEND_URL ?? '').replace(/\/+$/, '') ===
      PREPROD_URL
        ? 'preprod'
        : 'localhost-mock';

    const manifest: VerificationManifest = {
      schema: 'verification-manifest.schema.json#v1',
      spec: slug,
      run_id: RUN_ID,
      project: testInfo.project.name,
      target,
      base_url:
        process.env.PREPROD_FRONTEND_URL ?? 'http://localhost:3000',
      started_at: new Date().toISOString(),
      steps: [],
      forbidden_requests: [],
      interception: { route_registrations: 0, clean: true },
    };

    // ── Interception detection: any route() registration taints the run. ──
    // The fixture itself never calls route(), so a nonzero count means the
    // spec (or an imported helper like mock-api-data.ts) is mocking.
    let routeRegistrations = 0;
    const patchRoute = (obj: Page | BrowserContext): void => {
      const original = obj.route.bind(obj);
      (obj as { route: typeof obj.route }).route = ((...args) => {
        routeRegistrations += 1;
        return (original as (...a: unknown[]) => unknown)(...args);
      }) as typeof obj.route;
    };
    patchRoute(page);
    patchRoute(context);

    // ── Event capture (generalized from chaos-helpers console pattern). ──
    const allRequests: AuthRequestEntry[] = []; // full log, for forbid() rules
    let authSinceLastStep: AuthRequestEntry[] = [];
    let errorsSinceLastStep: AuthRequestEntry[] = [];
    let consoleSinceLastStep: string[] = [];
    let pageErrorsSinceLastStep: string[] = [];
    let mainStatus: number | null = null;

    page.on('response', (response) => {
      let pathname: string;
      try {
        pathname = new URL(response.url()).pathname;
      } catch {
        return;
      }
      // Normalize away deployment prefixes: on preprod the frontend calls
      // API Gateway whose paths carry a stage segment (/{stage}/api/v2/...).
      // A bare startsWith('/api/') filter recorded NOTHING on the target of
      // record - the exact blind spot this pipeline exists to prevent.
      const apiIdx = pathname.indexOf('/api/');
      if (apiIdx !== -1) {
        const normalized = pathname.slice(apiIdx);
        const entry: AuthRequestEntry = {
          method: response.request().method(),
          path: normalized,
          status: response.status(),
        };
        allRequests.push(entry);
        if (normalized.startsWith(AUTH_PATH_PREFIX)) {
          authSinceLastStep.push(entry);
        } else if (response.status() >= 400) {
          errorsSinceLastStep.push(entry);
        }
      }
      if (
        response.request().isNavigationRequest() &&
        response.frame() === page.mainFrame()
      ) {
        mainStatus = response.status();
      }
    });
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleSinceLastStep.push(msg.text());
    });
    page.on('pageerror', (err) => {
      pageErrorsSinceLastStep.push(String(err));
    });

    const rules: ForbiddenRequestRule[] = [];
    let counter = 0;

    const verify: Verify = {
      forbid(rule: ForbiddenRequestRule): void {
        rules.push(rule);
      },
      async shot(name, opts): Promise<void> {
        counter += 1;
        const nn = String(counter).padStart(2, '0');
        const file = `${slug}-${nn}-${name}.png`;
        await page.screenshot({
          path: path.join(dir, file),
          fullPage: true,
        });

        let probeResult: DomProbeResult | undefined;
        if (opts?.probe) {
          const loc = page.locator(opts.probe.selector).first();
          const present = (await loc.count()) > 0;
          let text: string | undefined;
          if (present) {
            text = (await loc.innerText().catch(() => '')) ?? '';
          }
          probeResult = {
            selector: opts.probe.selector,
            present,
            text,
            expect_text: opts.probe.expect_text,
            text_match:
              opts.probe.expect_text !== undefined
                ? (text ?? '').includes(opts.probe.expect_text)
                : undefined,
          };
        }

        manifest.steps.push({
          n: counter,
          name,
          file,
          expected_ui_state: opts?.expected_ui_state,
          page_url: page.url(),
          main_status: mainStatus,
          auth_requests: authSinceLastStep,
          api_errors: errorsSinceLastStep,
          console_errors: consoleSinceLastStep,
          page_errors: pageErrorsSinceLastStep,
          dom_probe: probeResult,
          timestamp: new Date().toISOString(),
          test_location: `${path.relative(
            frontendRoot(testInfo),
            testInfo.file
          )}:${testInfo.line}`,
          interception_at_capture: routeRegistrations > 0,
        });
        // reset per-step accumulators
        authSinceLastStep = [];
        errorsSinceLastStep = [];
        consoleSinceLastStep = [];
        pageErrorsSinceLastStep = [];
      },
    };

    await use(verify);

    // ── Teardown: evaluate forbidden_requests against the FULL request log. ──
    manifest.forbidden_requests = rules.map((rule) => {
      const observed = allRequests.filter(
        (r) =>
          r.method === rule.method &&
          r.path.includes(rule.path) &&
          (rule.status === undefined || r.status === rule.status)
      ).length;
      return { ...rule, observed_count: observed, pass: observed <= rule.max_count };
    });
    manifest.interception = {
      route_registrations: routeRegistrations,
      clean: routeRegistrations === 0,
    };
    manifest.finished_at = new Date().toISOString();

    fs.writeFileSync(
      path.join(dir, `${slug}.manifest.json`),
      JSON.stringify(manifest, null, 2)
    );
  },
});

export { expect };
