# Implementation Plan — Feature 1389 torch-rce-upgrade

**Spec:** `./spec.md`
**Branch:** `1389-torch-rce-upgrade`
**Scope:** One-line pin bump in `src/lambdas/analysis/requirements.txt`, rebuild the analysis
container image, prove inference parity on the real S3 model, verify image size, redeploy the
analysis Lambda. No new AWS resources; no dashboard/SSE/ingestion change.

---

## Technical Context

| Item | Value / Source |
|------|----------------|
| Vulnerability | CVE-2025-32434 / GHSA-53q9-r3pm-6pq6 — RCE via `torch.load` even with `weights_only=True` (CWE-502) |
| Severity | Critical, CVSS 9.3 |
| Affected | torch ≤ 2.5.1 (current pin `torch==2.5.1+cpu`, `requirements.txt:7`) |
| Fixed version | **2.6.0** (target `torch==2.6.0+cpu`) |
| Index | existing `--extra-index-url https://download.pytorch.org/whl/cpu` (official PyTorch CPU index — no new source) |
| Runtime | `public.ecr.aws/lambda/python:3.13`, linux/amd64, container image via ECR (`Dockerfile`) |
| Load path | `transformers.pipeline("sentiment-analysis", model=/tmp/model, framework="pt", device=-1)` (`sentiment.py:191-199`); artifact `s3://…/distilbert/v1.0.0/model.tar.gz` → `/tmp/model` |
| transformers | `transformers>=4.46.0,<5.0.0` (range; **no co-bump needed** — supports torch 2.6) |
| Lambda config | memory 2048 MB, ephemeral 3072 MB, timeout 120 s, reserved concurrency 5 (`main.tf:381-389`) — **unchanged** |
| Image-size limit | 10 GB uncompressed (AWS Lambda container limit) |
| Direct `torch.load` in app | **none** (grep of `src/lambdas/analysis/` → 0) → 2.6 `weights_only` default flip is app-safe |

> **Context7 status:** both Context7 MCP servers (primary + plugin) returned "Invalid API key"
> this session. Version facts were verified against the GitHub Advisory
> (GHSA-53q9-r3pm-6pq6 / CVE-2025-32434) and PyTorch/transformers primary sources. If Context7 is
> restored, re-verify (a) `2.6.0+cpu` cp313/linux-amd64 wheel presence on the CPU index, (b) the
> transformers torch-≥2.6 `torch.load` gate, and (c) any 2.5→2.6 model-loading breaking change.

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| Two-dashboard hazard | ✅ | Backend/analysis Lambda only. No `frontend/` or `src/dashboard/` touch. |
| No new AWS resources | ✅ | Edits one requirements line; rebuilds an existing image into the existing ECR repo; redeploys the existing Lambda. Zero new resources. |
| Analysis Lambda stays functional for alerting | ✅ | Parity gate (FR-004) + preprod-first (FR-008) + no-silent-fallback (FR-005) + rollback to previous image tag. |
| GPG-signed commits | ✅ | `git commit -S` for the pin change. |
| venv active for commits | ✅ | Standing rule honored (no `.tf` here, but keep venv active). |
| Least-diff | ✅ | One-line pin bump; transformers touched only if parity/gate forces it. |
| SAST / secrets | ✅ | No secrets; no new Python logic. Dependency-only change. |

**Result: PASS.** No violations.

---

## Approach

**Chosen: minimal pin bump + prove-it-loads gate + size guard + preprod-first redeploy.**

1. **Bump the pin.** `src/lambdas/analysis/requirements.txt:7`: `torch==2.5.1+cpu` →
   `torch==2.6.0+cpu`. Keep the `--extra-index-url .../whl/cpu` line. Leave transformers range
   as-is (FR-003 / C3).
2. **Capture the 2.5.1 parity baseline first.** Before changing anything, run a fixed set of
   representative inputs through the *current* image's `analyze_sentiment()` and record
   labels+scores. This is the oracle for FR-004; without it "parity" is unfalsifiable.
3. **Rebuild the image** (`cd src && docker build -f lambdas/analysis/Dockerfile .`). Confirm a
   clean `pip install` of `torch==2.6.0+cpu` from the CPU index (no CUDA wheels), and capture the
   resolved `pip freeze` inside the image as build evidence (transformers/numpy resolution — H1).
4. **Prove the model loads on 2.6 against the real artifact.** Inside the rebuilt container,
   download the actual `distilbert/v1.0.0/model.tar.gz`, extract, and call the same
   `pipeline("sentiment-analysis", …)`. Assert it loads (no `torch.load` gate error) and note the
   artifact format (safetensors vs `.bin`) — resolves C2.
5. **Run the parity set** through the 2.6 image; compare to the step-2 baseline: labels identical,
   scores within ±0.01 (FR-004). Mismatch → block, investigate (likely transformers resolution —
   tighten floor per FR-003).
6. **Measure image size** (`docker image inspect … --format '{{.Size}}'`); confirm < 10 GB and
   record delta vs the 2.5.1 image (FR-006). torch 2.6 CPU wheel is ~same order as 2.5.1 CPU;
   expected delta is small.
7. **Push to ECR and redeploy to preprod** via the normal pipeline (`aws lambda
   update-function-code`, per the `ignore_changes=[image_uri]` note at `modules/lambda/main.tf:113`).
   Exercise the inference path end-to-end (SNS trigger or direct invoke) and confirm sentiment is
   written and the alerting path is live (FR-008). Prod only after preprod is green.

**Rejected alternatives**
- *Bump to torch 2.7+ "while we're here":* larger, unvetted behavior/size delta for no extra
  security benefit (2.6.0 already patches CVE-2025-32434). Rejected — 2.6.0 is the minimal patched
  target; NFR-003.
- *Switch the artifact to safetensors now:* a real format-level hardening but out of scope, needs
  re-packaging the model, and is not required once torch ≥ 2.6. Deferred (spec §8).
- *Rely on the mocked CI suite as the parity check:* CI mocks torch/transformers
  (`requirements-ci.txt`), so it can't detect a real load/behavior regression. Rejected — parity
  must run in the real container/venv (M2).

---

## Version Targets & Compatibility Findings

| Package | Current | Target | Rationale / finding |
|---------|---------|--------|---------------------|
| torch | `2.5.1+cpu` | `2.6.0+cpu` | Patched version for CVE-2025-32434 (fixed 2.6.0). CPU wheel from existing index. If `2.6.0+cpu`/cp313 unavailable, lowest patched `2.6.x+cpu`. |
| transformers | `>=4.46.0,<5.0.0` | **unchanged** | Range already supports torch 2.6; loading `.bin` on torch ≥ 2.6 satisfies the transformers `torch.load` gate. Co-bump only if parity fails (FR-003). |
| numpy | (unpinned, transitive) | (resolver-chosen) | Pulled via torch/transformers; captured in image `pip freeze`; parity + size gates catch any bad resolution (H1). |

**Compat verdict:** No breaking change in the *application* model-load path is expected. torch 2.6
flips `torch.load(weights_only)` default False→True, but the app never calls `torch.load` directly
(grep = 0) — transformers owns that call. The one real behavioral gate is transformers' own
torch-≥2.6 requirement for `.bin` weights, which the upgrade *satisfies* rather than trips. The
single unverified fact is the S3 artifact's serialization format, converted into the FR-004
verification gate rather than an assumption.

---

## Files Touched

| File | Change |
|------|--------|
| `src/lambdas/analysis/requirements.txt` | `torch==2.5.1+cpu` → `torch==2.6.0+cpu` (line 7). Possibly a transformers floor bump **only if** FR-003 parity forces it. |

No Terraform change (config unchanged, FR-007). No handler/sentiment code change. The image is
rebuilt from the unchanged `Dockerfile`.

---

## Image-Size Verification Approach

1. Baseline: `docker image inspect <2.5.1-image> --format '{{.Size}}'` (or the last pushed ECR
   image size) recorded as the "before".
2. After rebuild: same command on the 2.6.0 image → "after".
3. Assert `after < 10 GB` (Lambda hard limit) and record `after - before`. Cross-check the torch
   wheel footprint inside the image (`du -sh /var/task/torch`).
4. If the delta is unexpectedly large (e.g. a CUDA wheel slipped in via a wrong index resolution),
   stop and inspect `pip freeze` / the install log — this is the H1/H2 tripwire, not a pass.

---

## Validation Strategy

**Static (pre-push):**
- `ruff`/existing pre-commit unaffected (no Python logic change).
- Confirm the requirements diff is exactly the torch line (+ transformers only if FR-003 forced it).

**Build-time (real torch 2.6, not mocked):**
- Clean `docker build` with `torch==2.6.0+cpu` installing from the CPU index; capture install log +
  in-image `pip freeze` (FR-002, H1).
- In-container real-artifact load + parity run vs the pre-change baseline (FR-004); record artifact
  format (C2).
- Image-size measurement < 10 GB with recorded delta (FR-006).

**Post-deploy (preprod, real AWS — FR-008):**
- Redeploy via `aws lambda update-function-code`; invoke the analysis Lambda end-to-end (SNS or
  direct) on a known input; confirm sentiment is written to the timeseries/sentiment table and the
  alerting path is exercised. Check the error alarm did **not** fire and CloudWatch shows a
  successful model load ("Model loaded successfully", `sentiment.py:203`).
- Confirm Dependabot alert #37 flips to resolved after merge/deploy.

**Rollback:** the analysis Lambda is a container image; roll back by pointing
`update-function-code` at the previous ECR image digest (the last known-good 2.5.1 image). No data
migration, fully reversible. Because promotion is gated on the parity run (FR-004) + preprod check
(FR-008), a broken image should never reach prod; if it somehow does, the previous digest restores
service immediately.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Model fails to load on 2.6 (format/gate) | Low–Med | Alerting inference down | FR-004 real-artifact load gate before any deploy; preprod-first; rollback to prior image digest. |
| Silent wrong sentiment (future fallback patch) | Low | Alerting silently degraded | FR-005: no fallback allowed; load failure raises `ModelLoadError` + error alarm + DLQ. |
| transformers/numpy resolves to a bad version on rebuild | Med | Behavior or size drift | FR-003 parity + FR-006 size gate; capture in-image `pip freeze` as evidence; tighten floor if needed. |
| `2.6.0+cpu` cp313 wheel absent on index | Low | Build fails | Fall back to lowest patched `2.6.x+cpu` (Assumptions §7); still ≥ 2.6.0, still patched. |
| Image exceeds 10 GB (e.g. CUDA wheel pulled) | Low | Deploy rejected | Size guard (FR-006) + `--extra-index-url` CPU build assertion + `pip freeze` inspection. |
| CI green but proves nothing (mocked) | Med | False confidence | Parity/verify runs in the real container/venv, not the mocked unit suite (M2). |
| Bad image reaches prod | Low | Alerting outage | NFR-005 preprod-first + parity gate; rollback via previous digest. |

---

## Adversarial Review #2

**Stance:** hunt for spec↔plan drift and cross-artifact contradictions after Clarify.

### Cross-artifact consistency

| Check | Spec | Plan | Consistent? |
|-------|------|------|-------------|
| Target version | `torch==2.6.0+cpu` (FR-001) | Version Targets table + Approach step 1 | ✅ |
| Patched-version source | CVE/GHSA fixed 2.6.0 (Problem, C1) | Technical Context table | ✅ |
| transformers no co-bump | FR-003 / C3 | Version Targets ("unchanged") + Compat verdict | ✅ |
| Artifact-format unknown → gate | FR-004 / C2 | Approach step 4, Validation build-time | ✅ |
| No silent fallback | FR-005 | Constitution, Risks row, rollback rationale | ✅ |
| Image-size guard | FR-006 | Image-Size Verification section | ✅ |
| Config unchanged / no new resources | FR-007, NFR-002 | Constitution, Files Touched (no `.tf`) | ✅ |
| Preprod-first real verify | FR-008 | Validation post-deploy | ✅ |
| weights_only flip app-safe | FR-009 / C4 | Compat verdict (grep=0) | ✅ |
| Baseline-before-change | FR-004 needs a baseline | Approach step 2 (capture 2.5.1 baseline first) | ✅ |
| Context7 unavailable, cite sources | Spec Context7 note | Plan Context7 status callout | ✅ |

### Drift findings

| ID | Sev | Finding | Resolution |
|----|-----|---------|-----------|
| D1 | MED | Spec FR-004 asserts "parity within ±0.01 of the 2.5.1 baseline" but the *baseline capture* is a plan/task step, not a spec FR — a reader could try to parity-check with no oracle. | Plan Approach **step 2** makes baseline capture the first action; tasks put it in Phase 0 before the pin bump. Recorded; no FR change (baseline is a task, the tolerance is the FR). |
| D2 | LOW | Spec says `2.6.0+cpu`; if the CPU index lacks a cp313 `2.6.0+cpu` build the pin can't be exactly `2.6.0`. | Both artifacts allow "lowest patched `2.6.x+cpu`" (spec Assumptions §7 / FR-001 "≥ 2.6.0"; plan Version Targets + Risks). Consistent, no contradiction. |
| D3 | LOW | Plan mentions capturing in-image `pip freeze`; spec has no explicit FR for it. | It's evidence for FR-003 (resolved transformers/numpy), not a separate requirement. INFO — no FR needed. |
| D4 | INFO | Root `requirements.txt` (`torch==2.13.0`) is excluded in both; consistent scoping (spec §8 / C5, plan Scope). | No action. |

### Gate
- CRITICAL: **0** · HIGH: **0** · Unresolved drift: **0** (D1/D2 clarified, D3/D4 info)

**PASS.** Spec and plan are consistent. No structural rework → Plan 2nd pass skipped.
