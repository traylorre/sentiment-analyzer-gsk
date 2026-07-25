# Tasks — Feature 1389 torch-rce-upgrade

**Spec:** `./spec.md` · **Plan:** `./plan.md` · **Branch:** `1389-torch-rce-upgrade`
**Nature:** Dependency bump + rebuild + verify + redeploy. Dependency-ordered. `[P]` = parallelizable with siblings.

> Planning artifact only. Do NOT execute (no `/speckit.implement`). Implementation happens in a later phase.

---

## Phase 0 — Baseline capture (the parity oracle)

- **T001** Capture the CVE evidence: record that `src/lambdas/analysis/requirements.txt:7` pins
  `torch==2.5.1+cpu` (affected ≤ 2.5.1) and that Dependabot alert #37 / CVE-2025-32434 is open.
  (Covers: FR-001 baseline, Success #2.)
- **T002** Build/run the **current** (2.5.1) analysis image and run a fixed representative input set
  through `analyze_sentiment()`; save labels+scores as the parity baseline oracle. Without this,
  FR-004 is unfalsifiable. (Covers: FR-004 baseline.)
- **T003 [P]** Record the current image size (`docker image inspect --format '{{.Size}}'` or last
  pushed ECR image) and current in-image `pip freeze` as the "before" for size/resolution deltas.
  (Covers: FR-006 baseline, H1.)

## Phase 1 — Bump the pin

- **T004** Edit `src/lambdas/analysis/requirements.txt:7`: `torch==2.5.1+cpu` → `torch==2.6.0+cpu`.
  Keep the `--extra-index-url https://download.pytorch.org/whl/cpu` line. Leave the transformers
  range unchanged. (Covers: FR-001, FR-003, US-1.)

## Phase 2 — Rebuild image + prove it installs/loads on real torch 2.6

- **T005** Rebuild: `cd src && docker build -f lambdas/analysis/Dockerfile -t analysis-2.6 .`.
  Assert a clean `pip install` of `torch==2.6.0+cpu` **from the CPU index** with no CUDA wheels;
  save the install log. If `2.6.0+cpu`/cp313 is unavailable, use the lowest patched `2.6.x+cpu` and
  record it. (Covers: FR-002, H2.)
- **T006** Capture the rebuilt image's `pip freeze` (torch/transformers/numpy resolution) as
  evidence and diff against the T003 "before". (Covers: FR-003, H1.)
- **T007** In the rebuilt container, download the **real** `distilbert/v1.0.0/model.tar.gz`,
  extract, and call `pipeline("sentiment-analysis", model=/tmp/model, framework="pt")`. Assert it
  loads with **no** `torch.load` gate error, and record the artifact serialization format
  (safetensors vs `pytorch_model.bin`). **This is the make-or-break load check.**
  (Covers: FR-004 load, C2, FR-009.)

## Phase 3 — Inference parity + size guard (the gates)

- **T008** Run the T002 parity input set through the 2.6 image; assert **every label identical** and
  **scores within ±0.01** of the baseline. Any mismatch → BLOCK, investigate (likely transformers
  resolution; tighten floor per FR-003). (Covers: FR-004, US-1, Success #3.)
- **T009 [P]** Measure the 2.6 image size; assert `< 10 GB` and record delta vs T003. Inspect
  `du -sh /var/task/torch` to confirm the CPU wheel footprint is sane (no CUDA bloat).
  (Covers: FR-006, US-2, Success #4.)
- **T010 [P]** Confirm no silent-fallback path exists/was added: `analyze_sentiment()` /
  `load_model()` still raise `InferenceError` / `ModelLoadError` on failure (no neutral/stale/mock
  fallback). (Covers: FR-005, US-3, Success #6.)

## Phase 4 — Commit

- **T011** GPG-signed commit of the requirements change **with venv active**:
  `source .venv/bin/activate && git commit -S`. Dependency-only. (Covers: NFR-004.)

## Phase 5 — Redeploy to preprod (real AWS) + end-to-end verification (FR-008)

- **T012** Push the 2.6 image to the existing analysis ECR repo and redeploy the analysis Lambda to
  **preprod** via `aws lambda update-function-code` (respects `ignore_changes=[image_uri]`,
  `modules/lambda/main.tf:113`). Confirm memory/ephemeral/timeout/concurrency and IAM/SNS are
  unchanged and **no new AWS resource** was created. (Covers: FR-007, FR-008, NFR-002, NFR-005.)
- **T013** Exercise the inference path end-to-end on preprod (SNS trigger or direct invoke) on a
  known input; confirm sentiment is written to the timeseries/sentiment table, CloudWatch shows
  "Model loaded successfully" (`sentiment.py:203`), and the error alarm did **not** fire — the
  alerting path is live. (Covers: FR-008, US-1, US-3, Success #5.)
- **T014 [P]** Confirm Dependabot alert #37 (CVE-2025-32434) flips to resolved after merge/deploy;
  no torch ≤ 2.5.1 remains in the deployed image. (Covers: FR-001, Success #1/#2.)

## Phase 6 — Prod (only after preprod green)

- **T015** Promote to prod via the normal pipeline only after T008/T009/T013 pass. Keep the previous
  ECR image digest recorded for one-command rollback (`update-function-code` to prior digest).
  (Covers: FR-008, NFR-005.)

---

## Requirement → Task coverage

| Requirement | Task(s) |
|-------------|---------|
| FR-001 (pin ≥ 2.6.0, no affected torch in image) | T001, T004, T012, T014 |
| FR-002 (2.6.0+cpu installs clean from CPU index) | T005 |
| FR-003 (transformers stays compatible; no forced co-bump) | T004, T006, T008 |
| FR-004 (inference parity on real artifact) | T002, T007, T008 |
| FR-005 (no silent fallback; load failure raises) | T010, T013 |
| FR-006 (image < 10 GB, delta recorded) | T003, T009 |
| FR-007 (config unchanged, no new resources) | T012 |
| FR-008 (redeploy + real-preprod verification) | T012, T013, T014, T015 |
| FR-009 (weights_only flip app-safe) | T007 |
| NFR-001 (full remediation, no weakened pins) | T004, T006 |
| NFR-002 (no infra growth) | T012 |
| NFR-003 (least diff) | T004 |
| NFR-004 (GPG, venv) | T011 |
| NFR-005 (availability; bad image never promoted) | T012, T015 |
| US-1 | T004, T008, T013 |
| US-2 | T009 |
| US-3 | T010, T013 |

Every requirement maps to ≥1 task; no task lacks a requirement.

---

## Analyze — cross-artifact consistency

- **Coverage:** 9 FR + 5 NFR + 3 US → all covered (table above). No orphan requirement; no
  unmapped task.
- **Ordering:** baseline (T001-3) → pin (T004) → rebuild/load (T005-7) → parity/size/fallback gates
  (T008-10) → commit (T011) → preprod deploy+verify (T012-14) → prod (T015). No forward-dependency
  violation. Critically, the **baseline (T002) precedes the pin bump (T004)** so parity has an
  oracle, and the **load/parity gates (T007-8) precede any deploy (T012)**.
- **Constitution:** unchanged from Plan — PASS (analysis-only, no new resources, no silent fallback,
  GPG+venv, preprod-first).
- **Terminology:** "parity", "2.6.0+cpu", "artifact format (safetensors vs `.bin`)", "image-size
  guard", "no silent fallback" consistent across spec/plan/tasks.
- **Ambiguities:** none open (Clarify resolved all 5; the only unknown — artifact format — is a
  verification task, T007, not a deferred question).

**Analyze result: consistent. No blocking issues.**

---

## Adversarial Review #3

**Stance:** find the task most likely to cause rework or a silent failed fix; decide readiness.

### Highest-risk task: **T007/T008 — real-artifact load + inference-parity regression**

**Why it's the crux, not T004:** T004 (the pin bump) is trivial and always "succeeds." The real
risk is a **model-load regression**: torch 2.6 changes `torch.load` behavior (default `weights_only`
flip) and transformers gates `.bin` loading on torch ≥ 2.6. If the S3 artifact
(`distilbert/v1.0.0/model.tar.gz`) interacts badly with the resolved torch+transformers pair, the
pipeline either (a) fails to load — caught loudly by `ModelLoadError` — or worse (b) loads but shifts
label/score outputs, silently degrading the alerting pipeline. The artifact's serialization format
could not be inspected from the repo (it lives in S3), so this is a genuine unknown, not a formality.

**Likely rework:** if T008 parity fails, the fix is *not* to revert the CVE patch — it's to pin the
transformers floor to a version that loads the artifact on torch 2.6 (FR-003), rebuild, and re-run
parity. That's a bounded second loop, contained entirely in the build/verify phases **before** any
deploy. Because T007/T008 gate T012, a parity failure is caught pre-deploy, converting a would-be
3am prod incident into a build-time BLOCK.

**Secondary risks:**
- **Baseline missing (T002 skipped):** parity becomes a vibe check. Mitigated by ordering — T002 is
  Phase 0, before the pin bump.
- **Mocked CI false-confidence (M2):** `requirements-ci.txt` mocks torch/transformers, so unit CI
  can't see a real regression. Guarded by running T007/T008 in the real container, and by making a
  green mocked CI explicitly insufficient for promotion.
- **Silent fallback sneaks in (C1/FR-005):** T010 asserts the raise-on-failure contract holds; the
  error alarm + DLQ (`main.tf:400-408`) make a load failure paged, not silent.
- **Image size / CUDA bloat (H1/H2):** T009 size guard + T005 CPU-index assertion + T006 `pip freeze`.

### Gate

| Criterion | Status |
|-----------|--------|
| Every requirement has a task | ✅ |
| Highest-risk task identified + mitigated pre-deploy | ✅ (T007/T008 gate T012; parity failure → tighten transformers floor, re-verify) |
| No open clarifications | ✅ (0 deferred; artifact format resolved by T007) |
| No silent-fallback path | ✅ (T010 + FR-005) |
| Constitution PASS | ✅ |
| CRITICAL / HIGH findings | 0 / 0 |

**READY FOR IMPLEMENTATION** (implementation deferred per battleplan — planning stops here).
