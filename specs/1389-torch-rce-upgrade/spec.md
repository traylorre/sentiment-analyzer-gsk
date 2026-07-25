# Feature 1389 — torch-rce-upgrade

**Status:** Draft (planning-only; no implementation)
**Branch:** `1389-torch-rce-upgrade`
**Type:** Security fix — dependency upgrade (analysis Lambda container image)
**Target:** ANALYSIS Lambda (container image via ECR). Production sentiment-inference path. NOT a dashboard change.
**Created:** 2026-07-24
**Tracking:** Dependabot alert #37 · CVE-2025-32434 · GHSA-53q9-r3pm-6pq6

---

## 1. Problem Statement

Dependabot alert #37 flags **CVE-2025-32434** (GHSA-53q9-r3pm-6pq6): a remote-code-execution
flaw in PyTorch's `torch.load`. The vulnerability defeats the `weights_only=True` safeguard —
the parameter long documented as the safe way to deserialize model weights **does not** prevent
RCE. A crafted model file triggers arbitrary code execution during deserialization (CWE-502).
Severity **Critical, CVSS 9.3**; no privileges or user interaction required.

**Fixed version:** PyTorch **2.6.0**. All versions **≤ 2.5.1 are affected.**
(Source: GitHub Advisory GHSA-53q9-r3pm-6pq6 / CVE-2025-32434.)

### Confirmed still present (verified, not re-derived)

`src/lambdas/analysis/requirements.txt:7` pins:

```
--extra-index-url https://download.pytorch.org/whl/cpu
torch==2.5.1+cpu
```

`2.5.1+cpu` is the CPU build of an affected version. This is the exact vulnerable pin.

### Why this Lambda is in the blast radius

The analysis Lambda **loads a model artifact from S3 in the production inference path**:

- `src/lambdas/analysis/sentiment.py:70-141` `_download_model_from_s3()` downloads
  `s3://…/distilbert/v1.0.0/model.tar.gz` and extracts it to `/tmp/model`.
- `sentiment.py:191-199` calls `transformers.pipeline("sentiment-analysis", model=path,
  tokenizer=path, framework="pt", device=-1)`. HuggingFace `transformers` deserializes the
  model weights; when the artifact is a pickle (`pytorch_model.bin`) this goes **through
  `torch.load`** — the exact vulnerable call.
- The Lambda is triggered by SNS on new ingested news (`main.tf:1054-1065`) and writes
  sentiment used by the alerting pipeline. A poisoned model artifact in the model S3 bucket
  would execute attacker code inside a production Lambda with the analysis role's permissions.

The app does **not** call `torch.load` directly (grep of `src/lambdas/analysis/` → zero
`torch.load` / `weights_only` references); the call is entirely inside `transformers`. That
matters for the torch 2.6 default-flip edge case (see Edge Cases / C4).

### Compatibility context (verified)

- **transformers pin:** `src/lambdas/analysis/requirements.txt:11` →
  `transformers>=4.46.0,<5.0.0` (a range, not a hard pin).
- **transformers now hard-gates on torch ≥ 2.6** for loading pickle (`.bin`) weights: recent
  `transformers` raises `ValueError` ("Due to a serious vulnerability issue in `torch.load`…
  we now require users to upgrade torch to at least v2.6") when asked to load `.bin` weights on
  torch < 2.6. The gate **does not apply to safetensors**. (Source: transformers modeling-utils
  torch.load safety check; HuggingFace issue reports, e.g. Hunyuan3D-2 #318.) This means the
  current pin is not only vulnerable, it is on a collision course: any transformers version bump
  that tightens the gate could make the **current** stack fail to load a `.bin` artifact — while
  upgrading torch to 2.6.0 both closes the CVE and satisfies the gate.

> Context7 note: both the primary and plugin Context7 MCP servers returned "Invalid API key"
> this session, so version facts above were verified against the GitHub Advisory
> (GHSA-53q9-r3pm-6pq6 / CVE-2025-32434) and PyTorch/transformers primary sources rather than
> Context7. Cited inline. If Context7 is restored, re-confirm (a) `2.6.0+cpu` presence on the
> CPU index and (b) the transformers torch-version gate.

---

## 2. Scope

**In scope**
- Bump the analysis Lambda pin from `torch==2.5.1+cpu` to `torch==2.6.0+cpu` (or the lowest
  patched CPU build ≥ 2.6.0) via the existing `--extra-index-url .../whl/cpu`.
- Rebuild the analysis container image and verify the DistilBERT model **still loads and
  produces the same labels/scores** on the actual S3 artifact (inference parity).
- Verify the rebuilt image stays within the Lambda container size limit (10 GB) and memory/
  ephemeral config is unchanged.
- Redeploy the analysis Lambda to preprod (then prod via the normal pipeline) and confirm the
  alerting inference path is functional after deploy.

**Out of scope**
- The root `requirements.txt` (`torch==2.13.0`, `transformers==4.57.6`) — a *separate* file for
  a separately-built layer/context, and `2.13.0` is not a real released torch version. Flagged as
  an open question (C5), not fixed here.
- Any dashboard, SSE, or ingestion Lambda.
- Migrating/re-training the model, or changing the model artifact format.
- Any new AWS resource.
- Changing Lambda memory, ephemeral storage, timeout, or concurrency (unless the size/parity
  check proves a required change — see FR-007).

---

## 3. User Scenarios

### US-1 (Primary) — Close the RCE without breaking inference
**As** the platform owner, **when** the analysis Lambda is upgraded to a patched torch, **then**
CVE-2025-32434 no longer applies **and** sentiment inference produces the same results it did on
2.5.1 for the same inputs — the alerting pipeline keeps working.

**Acceptance:**
- `src/lambdas/analysis/requirements.txt` pins `torch==2.6.0+cpu` (≥ 2.6.0).
- Dependabot alert #37 is resolved (no torch ≤ 2.5.1 remaining in the analysis image).
- The DistilBERT pipeline loads from the real S3 artifact and, on a fixed parity input set,
  returns labels identical to the 2.5.1 baseline and scores within a tiny tolerance.

### US-2 — Image still deployable
**As** an operator, **when** the image is rebuilt on torch 2.6.0+cpu, **then** it is under the
10 GB container-image limit and deploys to the existing ECR repo / Lambda with no config change.

### US-3 — No silent degradation at 3am
**As** on-call, **when** the model fails to load post-deploy for any reason, **then** the Lambda
**fails loudly** (raises `ModelLoadError`, error alarm fires) — it MUST NOT silently fall back to
stale, mocked, or neutral sentiment that would mask a broken inference path.

---

## 4. Functional Requirements

- **FR-001** `src/lambdas/analysis/requirements.txt` MUST pin torch to a patched CPU build
  **≥ 2.6.0** (target `torch==2.6.0+cpu`), installed via the existing
  `--extra-index-url https://download.pytorch.org/whl/cpu`. No torch ≤ 2.5.1 may remain in the
  built analysis image.
- **FR-002** The `2.6.0+cpu` wheel MUST resolve and install from the PyTorch CPU index for the
  Lambda base runtime (`public.ecr.aws/lambda/python:3.13`, linux/amd64) — verified by a clean
  `pip install` during image build (no CUDA wheels pulled).
- **FR-003** The transformers pin MUST remain compatible. `transformers>=4.46.0,<5.0.0` already
  admits versions that support torch 2.6, so **no co-bump is required**; however the resolved
  transformers version MUST be one that loads the model on torch 2.6 without the pre-2.6
  `torch.load` gate error. If (and only if) the resolved transformers version fails to load the
  artifact, the pin MUST be tightened to a compatible floor and that decision recorded.
- **FR-004 (inference parity)** After the upgrade, loading the **actual** S3 model artifact
  (`distilbert/v1.0.0/model.tar.gz`) MUST succeed, and running a fixed set of representative
  inputs through `analyze_sentiment()` MUST yield the **same label** for every input and scores
  within `±0.01` of the torch-2.5.1 baseline captured before the change. A parity mismatch is a
  release blocker.
- **FR-005 (no silent fallback)** The model-load path MUST continue to raise `ModelLoadError` on
  failure (`sentiment.py:213-218`). No fallback to neutral/stale/mock sentiment may be added.
  A load failure MUST surface as a Lambda error (DLQ + `create_error_alarm`), never as a quietly
  wrong result. This is a hard gate from AR#1.
- **FR-006 (image-size guard)** The rebuilt image size MUST be measured and MUST remain under the
  AWS Lambda container-image limit (10 GB uncompressed). The delta versus the 2.5.1 image MUST be
  recorded; torch 2.6 CPU is expected to be within a few percent of 2.5.1 CPU.
- **FR-007 (config unchanged, no new resources)** Memory (2048 MB), ephemeral storage (3072 MB),
  timeout (120 s), reserved concurrency (5), ECR repo, IAM role, and SNS wiring MUST be unchanged.
  No new AWS resource is introduced. Any config change would require explicit justification and is
  presumed out of scope.
- **FR-008 (redeploy + real-preprod verification)** After building and pushing the new image, the
  analysis Lambda MUST be redeployed to **preprod (real AWS)** and the inference path exercised
  end-to-end (SNS trigger or direct invoke) to confirm the model loads and sentiment is written —
  the alerting pipeline stays functional. Prod follows via the normal pipeline only after preprod
  is green.
- **FR-009 (weights_only default flip)** torch 2.6 changes the `torch.load` default `weights_only`
  from `False` to `True`. App code does not call `torch.load` directly, so this does not affect
  application code; the load happens inside `transformers`, which sets the flag itself. This MUST
  be confirmed by the successful parity run (FR-004), not assumed.

## 5. Non-Functional Requirements

- **NFR-001 (Security)** Remediate CVE-2025-32434 fully; do not weaken any other pin to force
  resolution. No new supply-chain surface beyond the already-trusted PyTorch CPU index.
- **NFR-002 (No infra growth)** Reuse existing ECR/Lambda/IAM/SNS. Zero new AWS resources
  (standing constraint).
- **NFR-003 (Least diff)** Prefer a one-line pin bump; touch transformers only if parity/gate
  forces it (FR-003).
- **NFR-004 (Deploy safety)** GPG-signed commits; venv active for commit (checkov `.tf` gotcha is
  N/A here since no `.tf` changes, but venv-active remains the standing commit rule); preprod-first,
  prod later.
- **NFR-005 (Availability during rollout)** The analysis Lambda must remain functional for
  alerting throughout — a bad image MUST NOT replace a working one without the parity gate passing.

## 6. Success Criteria

1. `torch==2.6.0+cpu` pinned in the analysis requirements; no torch ≤ 2.5.1 in the built image.
2. Dependabot alert #37 (CVE-2025-32434) resolved/closed.
3. DistilBERT loads from the real S3 artifact on 2.6.0; parity run matches the 2.5.1 baseline
   (labels identical, scores within ±0.01).
4. Rebuilt image < 10 GB; delta vs 2.5.1 recorded; Lambda config unchanged; no new resources.
5. Redeployed to preprod (real AWS); inference/alerting path verified green end-to-end before prod.
6. No silent-fallback path introduced; load failure still raises `ModelLoadError` + alarms.

## 7. Assumptions & Dependencies

- The PyTorch CPU index publishes a `2.6.0+cpu` linux/amd64 / cp313 wheel (to confirm at build
  time; the CPU index has carried per-release `+cpu` builds for 2.6.x). If `2.6.0+cpu` is
  unavailable for cp313, the lowest available patched CPU build ≥ 2.6.0 (e.g. 2.6.x) is used.
- The S3 model artifact `distilbert/v1.0.0/model.tar.gz` is loadable on torch 2.6 — **contingent
  on its serialization format** (safetensors vs `pytorch_model.bin`). Since the Lambda is
  currently functional on 2.5.1, the artifact loads today; torch 2.6 upgrade is expected to keep
  or improve compatibility (it also *satisfies* the transformers torch-≥2.6 gate for `.bin`). The
  parity task (FR-004) is the authoritative check; the artifact format is called out in C2.
- CI mocks torch/transformers (`requirements-ci.txt`), so parity MUST be validated in the built
  container (or a torch-2.6 venv), not by the mocked unit suite.

## 8. Out-of-Scope / Deferred

- Root `requirements.txt` torch/transformers cleanup (C5) — separate file, separately built,
  and `torch==2.13.0` is not a real version. Deferred to its own item.
- Switching the model artifact to safetensors (a stronger, format-level mitigation) — deferred;
  not required to close the CVE once torch ≥ 2.6.

---

## Adversarial Review #1

**Reviewer stance:** assume the "one-line bump" is a trap. Attack the supply chain, the dependency
cascade, silent load failure, and the 3am blast radius.

### Findings

| ID | Sev | Attack | Finding | Resolution |
|----|-----|--------|---------|-----------|
| C1 | CRITICAL | "The fix ships but inference silently breaks and nobody notices." | If `2.6.0` changes anything in the load path and the code had *any* fallback, the alerting pipeline would emit wrong/neutral sentiment while looking healthy. Reviewed `sentiment.py`: `load_model()` raises `ModelLoadError` (213-218) and `analyze_sentiment()` re-raises `InferenceError` (292-297) — **there is no fallback today.** The risk is a *future* well-meaning "resilience" patch adding one. | **FR-005 makes no-silent-fallback a hard requirement.** Load failure MUST raise + fire the error alarm (`create_error_alarm`, `main.tf:407-408`) + DLQ (`main.tf:400-401`). Parity gate (FR-004) must pass before the image is promoted. Resolved. |
| C2 | CRITICAL | "Model loads on 2.5.1 but not on 2.6 (or vice-versa) — format mismatch." | The S3 artifact's serialization format (`model.safetensors` vs `pytorch_model.bin`) determines whether torch 2.6's `weights_only=True` default and the transformers torch-≥2.6 gate matter. The artifact lives in S3 and could not be inspected from the repo. If it is a `.bin` pickle, 2.6 is *required* by transformers anyway; if safetensors, torch version is irrelevant to the gate. Either way 2.6 is the safe direction, but "loads fine" must be **proven on the real artifact**, not assumed. | **FR-004 mandates a parity run against the actual `distilbert/v1.0.0/model.tar.gz`.** T-tasks include inspecting the extracted artifact's format and asserting a successful `pipeline(...)` load on 2.6 before any deploy. Resolved to a verification gate; format recorded in C2 of Clarifications. |
| H1 | HIGH | "Bumping torch cascades transformers/numpy and breaks the build." | torch 2.6 has different transitive floors (notably numpy). transformers pin is a *range* (`>=4.46,<5`), so pip may resolve a newer transformers on rebuild; numpy is unpinned in the analysis reqs and pulled transitively. An unexpected resolution could change tokenizer/model behavior or blow image size. | **FR-003** requires the resolved transformers to load the artifact (else tighten the floor and record it); **FR-004** parity run catches behavior drift; **FR-006** catches size drift. Build must be reproducible — capture the resolved `pip freeze` of the image as evidence. Resolved via existing gates. |
| H2 | HIGH | "Is the PyTorch CPU index trustworthy / is the wheel even there for cp313?" | Supply chain: `--extra-index-url https://download.pytorch.org/whl/cpu` is the official PyTorch index (already trusted by the current 2.5.1 pin — not a new source). Residual risk is only *availability* of `2.6.0+cpu` for python 3.13/linux-amd64. | No new index is introduced (NFR-001). **FR-002** verifies a clean install of the exact `+cpu` build at image-build time; if `2.6.0+cpu`/cp313 is absent, fall back to the lowest patched `2.6.x+cpu` (Assumptions §7). Resolved. |
| M1 | MED | "torch 2.6 flips `weights_only` default → app breaks." | App never calls `torch.load` directly (grep = none); the call is inside transformers, which passes its own flag. | **FR-009**: documented, and *proven* by the FR-004 parity run rather than assumed. No app change. |
| M2 | MED | "CI is green but proves nothing." | `requirements-ci.txt` mocks torch/transformers, so the unit suite never exercises real 2.6 loading. | Parity/verification MUST run in the built container or a real torch-2.6 venv (Assumptions §7, tasks Phase 2/3). A green mocked CI is explicitly **not** sufficient to promote. |
| M3 | MED | "3am: image promoted, model fails to load, alerting goes dark." | Blast radius if a bad image reaches prod. | NFR-005 + FR-008: preprod-first with an end-to-end inference check before prod; parity gate blocks promotion; error alarm + DLQ make a load failure loud and paged, not silent (ties to FR-005). Rollback = redeploy previous image tag (plan). Resolved. |

### Gate
- CRITICAL: **0** (C1 resolved by FR-005; C2 resolved by FR-004 parity gate)
- HIGH: **0** (H1 resolved by FR-003/004/006; H2 resolved by FR-002 + no-new-index)

**PASS — 0 CRITICAL / 0 HIGH.** Proceed to Plan.

---

## Clarifications

Self-answered from the codebase + cited sources (no owner input required). Max 5.

**C1 — What is the exact patched version, and is the current pin actually affected?**
Resolved. CVE-2025-32434 / GHSA-53q9-r3pm-6pq6: all torch **≤ 2.5.1 affected**, **fixed in 2.6.0**,
Critical CVSS 9.3, RCE via `torch.load` even with `weights_only=True` (CWE-502). Current pin
`torch==2.5.1+cpu` (`requirements.txt:7`) is affected. Target = `torch==2.6.0+cpu`.
(Source: GitHub Advisory GHSA-53q9-r3pm-6pq6.)

**C2 — Does the model artifact go through the vulnerable `torch.load`, and in what format?**
Resolved (partially — format is an S3 fact). The load path is
`transformers.pipeline("sentiment-analysis", model=/tmp/model, framework="pt")`
(`sentiment.py:191-199`). transformers deserializes weights; a `pytorch_model.bin` artifact routes
through `torch.load` (vulnerable), a `model.safetensors` artifact does not. The artifact
(`distilbert/v1.0.0/model.tar.gz`) is in S3 and its format is not visible from the repo, so **FR-004
requires inspecting the extracted artifact and proving a successful load on torch 2.6.** Regardless
of format, torch 2.6 is the correct target: it closes the CVE and satisfies the transformers
torch-≥2.6 gate that applies to `.bin`.

**C3 — Does transformers need a co-bump?**
Resolved. **No.** `transformers>=4.46.0,<5.0.0` (`requirements.txt:11`) is a range that already
admits versions supporting torch 2.6. The only requirement is that the *resolved* version loads the
artifact without the pre-2.6 `torch.load` gate error (FR-003); on torch 2.6 that gate is satisfied.
Co-bump only if the parity run fails, in which case tighten the floor and record it.
(Source: transformers modeling-utils torch-version gate; HuggingFace issue reports.)

**C4 — Does torch 2.6's `weights_only=True` default flip break the app?**
Resolved. No app impact. Grep of `src/lambdas/analysis/` finds **zero** direct `torch.load` /
`weights_only` uses — the load is entirely inside transformers, which manages the flag. Confirmed by
the FR-004 parity run rather than assumed (FR-009).

**C5 — The root `requirements.txt` pins `torch==2.13.0` / `transformers==4.57.6` — is that in scope?**
Resolved: **out of scope, flagged.** That file is separate (comment: "torch is large ~2GB; Lambda
layer built separately") and `2.13.0` is not a real released torch version (torch went 2.5 → 2.6 →
2.7…), so it is almost certainly a stale/aspirational or mistaken pin, not the vulnerable production
path. This feature fixes only `src/lambdas/analysis/requirements.txt`, the confirmed vulnerable
container pin. The root file is deferred to its own cleanup item (Out-of-Scope §8).

**Deferred to owner:** none blocking. The only unknown (artifact serialization format, C2) is
resolved by a verification task, not owner input.
