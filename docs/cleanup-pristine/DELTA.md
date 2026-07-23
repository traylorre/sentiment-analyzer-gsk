# Delta: Pristine (cold) run vs Seeded (prior-driven) run

Two maps of the same repo. `docs/cleanup/` was produced by a run seeded with a carryover's
known-findings. `docs/cleanup-pristine/` was produced by the same methodology run COLD: finders
got category directives only, computed their own ground truth, and never saw a prior finding.

The question was not "which is more accurate." Both are accurate where they looked. The question
was: **what did the seeded priors bury?** The delta answers it.

## Headline

The delta is almost entirely one-directional. The cold run found roughly **50+ real issues the
seeded run never surfaced**, and the cold run **refuted zero** of the seeded run's confirmed
claims. The seeded priors did not make the first run assert false things. They narrowed its
aperture so it never examined most of the repo. This is contamination by omission, not by
falsehood, and it is the more dangerous kind because a precision score cannot see it.

A seeded run that is 95% precise on the 15 things it looked at still missed ~75% of the real
issues. Optimizing for coverage-percentage would have scored the seeded run as excellent.

## Bucket 1: pristine found it, seeded missed it (the buried findings)

| Domain | Buried finding | Evidence |
|---|---|---|
| deadcode | ~11 production-orphaned modules (referenced ONLY by tests), vs the seeded run's single `storage.py` | `ingestion/collector.py`, `ingestion/audit.py`, `ingestion/adapters/base.py`, `notification/alert_evaluator.py`, `shared/auth/audit.py`, `shared/schemas.py`, `sse_streaming/resolution_filter.py`, `lib/deduplication.py`, `lib/timeseries/preload.py`, `errors_module` convenience fns + `ErrorCode`, `shared/utils` re-exports. Spot-verified: `collector.py` and `schemas.py` have zero production importers. |
| urls | Cognito frontend config object emitted + parsed but never referenced | `constants.ts:3` `COGNITO_CONFIG` defined, `grep COGNITO_CONFIG frontend/src` returns only the definition |
| urls | Next.js same-origin SSE proxy route is permanently dead (always 503) | `app/api/sse/[...path]/route.ts:30` needs `SSE_LAMBDA_URL`, never emitted to Amplify (`amplify/main.tf:62-72`) |
| urls | `NEXT_PUBLIC_USE_SSE_PROXY` consumed but never emitted, so the cookie-auth SSE path is dead code | `use-sse.ts:106` reads it; `grep USE_SSE_PROXY infrastructure/terraform` returns nothing (spot-verified) |
| comments | Terraform timeseries comment asserts "8 resolutions" with 8 TTLs; the enum has 6 | `dynamodb/main.tf:526,547` vs `lib/timeseries/models.py:24-29` |
| comments | `fanout.py` docstrings assert "8 resolutions"; same 6-member enum | `fanout.py` docstrings vs the enum |
| comments | `by_tag` GSI comment asserts a fan-out behavior that no code implements | `dynamodb/main.tf` by_tag comment, no matching code |
| validators | `tfsec` orphaned (removed from pre-commit, survives as a soft-fail command guard) | seeded run never mentioned tfsec |
| validators | `pip-audit` runs in CI but non-blocking (advisory only) | seeded run never mentioned pip-audit |
| validators | Systemic root cause: no workflow runs `pre-commit run` or `make`, so every pre-commit-only validator is CI-dark by construction | pristine articulated the mechanism, not just the symptom |
| manifest | `dev.tfvars` is vestigial (dev environment removed from the deploy pipeline) | deploy.yml deploys preprod then prod only |
| manifest | `ENVIRONMENT` is never `dev` in any deployed environment, which is WHY the HTMX dashboard is dead in prod (the dev-gate never opens) | resolves half of Q-HTMX that the seeded run left fully open |
| charts | 34 confirmed diagram drifts across 8 current-architecture files. The seeded run had NO chart domain at all (0). | see `diagram-drift.md` |

## Bucket 2: seeded asserted it, pristine did not reproduce it (contamination artifacts)

Near-empty, which is the important result. The cold run did not refute a single seeded CONFIRMED
claim. The only seeded-only items are scope differences, not errors:

- Two latent RUNTIME bugs (cross-source dedup tz mismatch; `/api/v2/runtime` dev-only SSE exposure).
  The pristine deadcode domain was scoped to dead code, not runtime bugs, so it did not target
  these. Both remain real per the seeded run's citations. Keep them.
- The root GitHub-Pages `index.html` stub. Pristine deferred it to an UNKNOWN "secondary surface"
  rather than classifying it. Not a contradiction, just less resolved.

No seeded finding was found to be a fabrication of its priors. The seeded run was honest; it was
just blinkered.

## Bucket 3: agreement (robust to priors)

Dashboard Function URL DISABLED; SSE Lambda URL LIVE; API Gateway LIVE and frontend-consumed;
Amplify LIVE; `/api/v2/runtime` SSE exposure is dev-only (both runs); the `source_id` example
comment and `by_status` `projection=ALL` comment and the `/opt/model` docstring are all misleading;
both WAF WebACLs LIVE and associated; Q-HTMX left UNKNOWN; and ~12 validators' run-states match.
This core is trustworthy precisely because it survived with and without priors.

## What this proves about method

1. **Seeded priors bury, they do not corrupt.** The danger is the ~50 issues never examined, not
   a handful of wrong assertions. A precision metric is blind to this failure mode.
2. **The narrow revisit would have made it worse.** Extending the seeded run (more passes on the
   same priors) would have deepened confidence in a map that was missing most of the territory.
   Only a cold re-derivation surfaced the buried class.
3. **The refute step catches tool error, including our own.** The import-graph false positives
   (bare imports in Docker-flattened layouts) were caught by the skeptic in both the narrow and
   pristine runs. Tool output is a suspect too.
4. **Charts are the highest-yield domain and were entirely absent from the seeded run.** 34-56
   drifts, several describing deleted code (chaos docs) or giving wrong operational guidance.

## Recommendation

Treat `docs/cleanup-pristine/` as the trustworthy map and retire `docs/cleanup/` as the
contamination baseline (keep it only as the evidence that priors narrow the search). Run the
execution phase off the pristine maps. Every pristine ORPHANED module is a candidate requiring
per-file adjudication, not an automatic delete: test-only code is either a dead feature or a
feature whose production wiring was never connected. Both are worth knowing.
