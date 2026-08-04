# Resume-Priority Brief — cleanup items that unlock resume claims

**From:** the resume-matcher session (Amazon SDE II application, 2026-07-24)
**Purpose:** overlay a priority lens on the existing cleanup work. These CLEANUP-BOARD
cards, if landed, unlock specific verifiable claims on Scott's Amazon SDE II resume.
This does NOT change your cleanup constraints (no new AWS resources without asking,
analysis Lambda untouched, append-only history, GPG-signed, no push until local-green).
It only says: *if you're choosing what to do next, these have outsized external value.*

Ranked by (resume claim strength) ÷ (effort). Each has an acceptance bar that must be
true before the resume will make the claim — the resume session will re-check the board /
the commit before asserting anything.

---

## P1 — LB-1: cross-source dedup merge never fires (board lane: fix, HIGH)

**Why it's #1:** best claim-value-per-hour on the whole board. The fix is tiny; the story
is a premium "Dive Deep" narrative — a content-addressed dedup key that was designed
correctly but silently never merged, because two feed adapters serialized timestamps
differently (Tiingo tz-aware `+00:00` vs Finnhub naive `fromtimestamp`), so the DynamoDB
sort keys never matched and duplicates were written instead of merged. Silent
data-correctness failure → root-caused to a serialization asymmetry → one-line fix.

**Board evidence (already VERIFIED):** tiingo.py:237-239 parses tz-aware; finnhub.py:227
uses naive `datetime.fromtimestamp()`; handler.py:1005 builds SK via
`published_at.isoformat()`; dedup.py:196-197 `update_item` creates a second row.

**Fix (per board next_action):** normalize Finnhub parse to
`datetime.fromtimestamp(item['datetime'], tz=timezone.utc)`, audit finnhub.py:388 for the
same pattern, add a cross-source merge test proving one story from both feeds collapses to
one item.

**Acceptance bar for the resume claim:** the normalization is committed AND a test exists
that fails before / passes after (proving the merge now fires). Then the resume can say
Scott root-caused AND fixed it. (The root-CAUSE is already assertable today; only "fixed"
waits on this.)

**Resume bullet it unlocks:**
> Root-caused a silent dedup failure: two news feeds serialized timestamps differently, so
> DynamoDB sort keys never matched and duplicates were stored instead of merged; fixed with
> one-line timestamp normalization.

---

## P2 — The 4 critical CVEs (board lane: fix, CRITICAL ×4)

**Why:** turns into a quantified security-ops claim, and two of the four are genuinely
resume-worthy because of WHERE they sit:
- next.js middleware auth bypass (CVE-2025-29927) — on the **customer dashboard** (Amplify).
- torch RCE via torch.load (CVE-2025-32434) — in the **production inference path** (analysis
  Lambda loads model artifacts from S3).
- basic-ftp (CVE-2026-27699) and vitest (CVE-2026-47429) — round out the "4 critical."

**Fixes (per board):** bump next ≥14.2.25 (frontend build + Playwright + Amplify deploy);
torch ≥2.6.0 (verify model load + Lambda image size, redeploy analysis Lambda — NOTE: this
touches the analysis Lambda's requirements; treat the "analysis Lambda untouched for
alerting" constraint as about behavior/wiring, but CONFIRM with the owner before redeploy);
basic-ftp via npm overrides; vitest bump + re-run suite.

**Acceptance bar:** the four bumps are committed and CI is green (or local suites pass where
CI can't run). Optionally also land the high-tier batch (transformers ×6, next ×7, vite ×3)
for a stronger "burned down the backlog" tail.

**Resume bullet it unlocks:**
> Patched 4 critical CVEs, including an RCE in the model-loading path and a middleware auth
> bypass on the customer dashboard, then burned down the dependency backlog.

---

## P3 — Make the dark validators actually gate (board lane: fix, MEDIUM ×2)

**Why:** integrity, not a standalone bullet. The resume's IAM-validator / "machine review
gates every deploy" bullet is stronger and more honestly stated if the gates actually run
server-side. Today: no CI job runs pre-commit (detect-secrets/trivy/checkov/mypy are
local-only), and pip-audit is advisory (`|| true` + continue-on-error).

**Fixes (per board):** uncomment the `pre-commit run --all-files` CI block
(.pre-commit-config.yaml:179-184 referenced); remove `|| true` + `continue-on-error: true`
from the pip-audit security job (pr-checks.yml:136-177).

**Acceptance bar:** CI actually runs these on PRs. Low effort (~30-60 min), high honesty
payoff for the existing IAM-governance bullet.

---

## Explicitly NOT resume-priority (still fine to do for cleanup's own sake)
- Q8 user alerts (day-plus build), by_tag GSI writer (weak story), Terraform drift import
  (#491, table stakes), the TD-01x portability issues, doc-drift stamping. Do them if
  cleanup wants them; they don't unlock a resume claim.

## How to signal back
When P1/P2/P3 land, Scott will notify the resume session (likely "check the kanban board").
The resume session will confirm the specific card is done / the commit exists before
asserting any claim — so moving the card to the **done** lane with the commit SHA in its
evidence is the handshake. No claim ships on intent; only on landed, verifiable work.
