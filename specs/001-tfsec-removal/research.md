# Research: Remove tfsec from the Security Validation Chain

**Feature**: 001-tfsec-removal | **Date**: 2026-07-29

No NEEDS CLARIFICATION markers existed in the Technical Context; research questions below were raised and settled during Phase 0 and AR#1.

## R1: Is tfsec actually superseded, or does removing it lose coverage?

- **Decision**: Removal loses zero effective coverage.
- **Rationale**: tfsec's maintainers (Aqua Security) folded tfsec into Trivy; tfsec never gained Terraform 1.5 `check`-block support (recorded in `.pre-commit-config.yaml:68` at the time of its pre-commit removal, and in `docs/cleanup-pristine/validator-inventory.md:37`). The surviving Makefile invocation runs `--soft-fail`, so even where it runs, findings cannot block. Effective IaC coverage today is the pre-commit `trivy-terraform` hook (report-only, `--exit-code 0`, flip owned by 1400 follow-up) and `checkov-terraform` (gating in the CI pre-commit job). Deleting a scanner that cannot fail changes no outcomes (verified reasoning in AR#1 F6/VERIFIED-OK).
- **Alternatives considered**: (a) Replace the Makefile tfsec line with a `trivy config` invocation — rejected: duplicates the pre-commit hook, and gating decisions for trivy are 1400's scope; (b) keep tfsec but remove `--soft-fail` — rejected: deprecated tool, would add a gate on an unmaintained scanner.

## R2: Which tfsec references are in scope for the sweep?

- **Decision**: In scope: `Makefile:70` (delete), `CONTRIBUTING.md:309` (correct), `SPEC.md:479` (correct), CLEANUP-BOARD.html tfsec card (lane move at completion). Out of scope: `.specify/memory/constitution.md:68` (own amendment process; recorded follow-up), `.pre-commit-config.yaml:67-69` (accurate historical rationale), `docs/archived-specs/**`, `docs/reviews/**`, `docs/cleanup-pristine/**` (historical/audit records), `specs/1400-validator-gating/spec.md:105` (another spec's scope note).
- **Rationale**: AR#1 performed the exhaustive repo-wide inventory (`grep -rl tfsec` excluding .git/.venv/node_modules) and confirmed no other surfaces exist: no workflow, no script, no install path, no aqua config references tfsec.
- **Alternatives considered**: Sweeping the constitution in the same commit — rejected (F1/F2): the constitution is governance with its own amendment process; bundling it into a toolchain fix commit would bypass that process.

## R3: How to verify "output identical with and without tfsec installed" on one machine?

- **Decision**: PATH shadowing. Run `make security` once with the real PATH, once with PATH filtered to exclude `~/.local/bin` (or with a sanitized PATH containing only system dirs + venv), capture both, `diff`.
- **Rationale**: Uninstalling the user-level binary is out of scope (spec Assumption); PATH manipulation reproduces the "not installed" condition exactly as the `command -v tfsec` guard perceives it.
- **Alternatives considered**: temporary rename of the binary — rejected: mutates state outside the repo; a crash mid-verification leaves the developer's machine altered.

## R4: Does anything downstream parse `make security` output?

- **Decision**: No consumer exists; output-shape change (one fewer possible line) is safe.
- **Rationale**: AR#1 verified no CI workflow, script, or doc invokes `make security` (only a comment at `pr-checks.yml:13` references `make validate` as a local-parity suggestion).
- **Alternatives considered**: N/A.
