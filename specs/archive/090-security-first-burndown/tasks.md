# Tasks: Security-First Drift Burndown

**Input**: Design documents from `/specs/090-security-first-burndown/`
**Prerequisites**: plan.md, spec.md (with clarification answers)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)

## Path Conventions

- **Single project**: `src/`, `tests/`, `infrastructure/` at repository root
- Target files listed per task

---

## Phase 1: Setup (Prerequisites & Documentation)

**Purpose**: Document prerequisites and prepare bootstrap steps

- [ ] T001 Document IAM user creation prerequisites in `specs/090-security-first-burndown/quickstart.md`
  - Include AWS Console steps for creating `preprod-sentiment-deployer`, `prod-sentiment-deployer`
  - Include `aws iam create-user` CLI commands as alternative
  - Include access key generation and GitHub secrets update steps

- [ ] T002 Create feature branch `090-security-first-burndown`

---

## Phase 2: User Story 1 - IAM Migration (P1)

**Goal**: Migrate legacy IAM ARN patterns to `*-sentiment-*` format

**Prerequisite**: Admin must first create new IAM users manually (T001)

**Independent Test**: `make check-iam-patterns`

### Implementation for User Story 1

- [ ] T003 [US1] Update IAM policy ARN patterns in `infrastructure/terraform/ci-user-policy.tf`
  - Change `arn:aws:iam::*:user/sentiment-analyzer-*-deployer` to `arn:aws:iam::*:user/*-sentiment-deployer`
  - Change `arn:aws:s3:::sentiment-analyzer-terraform-state-*` to `arn:aws:s3:::*-sentiment-tfstate`
  - Change `arn:aws:kms:*:*:alias/sentiment-analyzer-*` to `arn:aws:kms:*:*:alias/*-sentiment-*`

- [ ] T004 [US1] Remove legacy `sentiment-analyzer-*` patterns from policy
  - Ensure only `*-sentiment-*` patterns remain

- [ ] T005 [US1] Run `make check-iam-patterns` and verify 0 legacy errors

- [ ] T006 [US1] Update GitHub secrets via `gh secret set` (after admin creates users)
  - `gh secret set AWS_ACCESS_KEY_ID -b "..."`
  - `gh secret set AWS_SECRET_ACCESS_KEY -b "..."`

**Checkpoint**: `make check-iam-patterns` passes with 0 legacy errors

---

## Phase 3: User Story 2 - SRI Implementation (P1)

**Goal**: Add Subresource Integrity to CDN scripts

**Independent Test**: `grep -c integrity src/dashboard/*.html`

### Implementation for User Story 2

- [ ] T007 [P] [US2] Generate SRI hash for Tailwind CSS CDN
  - `curl -s https://cdn.tailwindcss.com | openssl dgst -sha384 -binary | openssl base64 -A`
  - Document hash and version

- [ ] T008 [P] [US2] Generate SRI hash for DaisyUI CDN
  - `curl -s https://cdn.jsdelivr.net/npm/daisyui@4.12.14/dist/full.min.css | openssl dgst -sha384 -binary | openssl base64 -A`
  - Document hash and version

- [ ] T009 [P] [US2] Generate SRI hash for Chart.js CDN
  - `curl -s https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js | openssl dgst -sha384 -binary | openssl base64 -A`
  - Document hash and version

- [ ] T010 [US2] Update `src/dashboard/index.html` with SRI attributes
  - Add `integrity="sha384-..."` and `crossorigin="anonymous"` to chart.js script tag

- [ ] T011 [US2] Update `src/dashboard/chaos.html` with SRI attributes
  - Add SRI to tailwind script tag
  - Add SRI to daisyui link tag

**Checkpoint**: All CDN scripts have integrity and crossorigin attributes

---

## Phase 4: User Story 3 - SRI Methodology (P1)

**Goal**: Create `/sri-validate` methodology via `/add-methodology`

**Prerequisite**: Template repo methodology structure understood (Phase 0 research)

**Independent Test**: `ls .claude/commands/sri-validate.md`

### Implementation for User Story 3

- [ ] T012 [US3] Create `.specify/methodologies/index.yaml` (methodology registry)
  - Copy structure from template repo
  - Add `sri_validation` entry

- [ ] T013 [US3] Create `src/validators/sri.py` (SRI validator)
  - Detection patterns for missing integrity on CDN scripts
  - Support for configurable excludes (node_modules, test fixtures)
  - Severity: MEDIUM
  - Follow BaseValidator pattern from template

- [ ] T014 [US3] Create `tests/unit/test_sri_validator.py` (validator tests)
  - Test positive case: CDN script without integrity detected
  - Test negative case: CDN script with integrity passes
  - Test exclusion: node_modules ignored
  - Test false positive: local scripts without integrity OK

- [ ] T015 [US3] Create `.claude/commands/sri-validate.md` (slash command)
  - Follow template pattern
  - Reference validator and methodology

- [ ] T016 [US3] Create `docs/sri-methodology.md` (documentation)
  - SRI best practices from canonical sources
  - Hash generation instructions
  - Troubleshooting guide

- [ ] T017 [US3] Add SRI hash check job to `.github/workflows/pr-checks.yml`
  - Detect if CDN content changed (hash mismatch)
  - Alert if update needed

**Checkpoint**: `/sri-validate` command runs and detects missing SRI

---

## Phase 5: User Story 4 - CSP Headers (P2)

**Goal**: Add Content Security Policy headers to CloudFront

**Prerequisite**: Check existing CloudFront response headers policy

**Independent Test**: Terraform plan shows `content_security_policy`

### Implementation for User Story 4

- [ ] T018 [US4] Check existing CloudFront response headers policy
  - Read `infrastructure/terraform/modules/cloudfront/main.tf`
  - Document existing security headers (HSTS, X-Frame-Options, etc.)

- [ ] T019 [US4] Add CSP to CloudFront response headers policy in Terraform
  - Extend existing policy (don't replace)
  - CSP: `default-src 'self'; script-src 'self' cdn.tailwindcss.com cdn.jsdelivr.net 'unsafe-inline'; style-src 'self' cdn.jsdelivr.net 'unsafe-inline'`

- [ ] T020 [US4] Run `terraform plan` and verify CSP header is added

- [ ] T021 [US4] Test CloudFront response includes CSP header (after apply)

**Checkpoint**: CloudFront returns Content-Security-Policy header

---

## Phase 6: User Story 5 - Dockerfile Security (P2)

**Goal**: Add non-root USER to SSE Lambda Dockerfile

**Independent Test**: `grep -c "USER lambda" src/lambdas/sse_streaming/Dockerfile`

### Implementation for User Story 5

- [ ] T022 [US5] Add lambda user creation to `src/lambdas/sse_streaming/Dockerfile`
  - `RUN adduser --disabled-password --gecos '' --uid 1000 lambda`

- [ ] T023 [US5] Add USER directive before CMD
  - `USER lambda`

- [ ] T024 [US5] Build Docker image locally and verify
  - `docker build -t sse-test src/lambdas/sse_streaming/`
  - Verify user is `lambda` not `root`

- [ ] T025 [US5] Test /tmp write access as lambda user
  - Container must be able to write to /tmp for model downloads

**Checkpoint**: Dockerfile runs as non-root lambda user

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [ ] T026 Run `make validate` to verify all checks pass
- [ ] T027 Run `make check-iam-patterns` to verify 0 legacy errors
- [ ] T028 Run `/sri-validate` to verify SRI methodology works
- [ ] T029 Update RESULT4-drift-audit.md with resolved findings
- [ ] T030 Update RESULT3-deferred-debt-status.md with 090 completion

**Checkpoint**: All success criteria met (SC-001 through SC-006)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **IAM (Phase 2)**: Depends on admin creating users (manual prerequisite)
- **SRI HTML (Phase 3)**: Can run in parallel with IAM
- **SRI Methodology (Phase 4)**: Can start after T009 (hashes generated)
- **CSP (Phase 5)**: Can start anytime
- **Dockerfile (Phase 6)**: Can start anytime
- **Polish (Phase 7)**: Depends on all user stories complete

### Parallel Opportunities

**Within Phase 3 (SRI)**:
- T007, T008, T009 can run in parallel (hash generation for different CDNs)

**Across Phases**:
- Phase 3 (SRI HTML) + Phase 5 (CSP) + Phase 6 (Dockerfile) can run in parallel
- Phase 2 (IAM) requires manual prerequisite but Terraform changes can be prepared

---

## Success Metrics

| Metric | Target | Verification Command |
|--------|--------|---------------------|
| IAM legacy patterns | 0 | `make check-iam-patterns \| grep LEGACY \| wc -l` |
| CDN scripts with SRI | 3 | `grep -c integrity src/dashboard/*.html` |
| SRI methodology exists | 1 | `ls .claude/commands/sri-validate.md` |
| CSP header configured | 1 | `terraform plan \| grep -c content_security_policy` |
| Dockerfile non-root | 1 | `grep -c "USER lambda" Dockerfile` |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Admin IAM user creation is a manual prerequisite (documented in T001)
- Commit after each phase or logical group
