# Tasks: Fix Architecture Diagram Inconsistencies

**Input**: Design documents from `/specs/1215-fix-diagram-inconsistencies/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete)

**Tests**: Not explicitly requested - focusing on documentation and script implementation with validation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- Documentation at repository root and in docs/
- Script in scripts/
- Source documentation in src/

---

## Phase 1: Setup

**Purpose**: Ensure working environment and understand current state

- [x] T001 Verify on branch 1215-fix-diagram-inconsistencies with latest main merged
- [x] T002 Read current README.md High-Level System Architecture diagram (lines 191-316)
- [x] T003 [P] Read current docs/diagrams/architecture.mmd

**Checkpoint**: Current state understood, ready to make changes

---

## Phase 2: User Story 4 - Maintainers Regenerate Mermaid Links Reliably (Priority: P1)

**Goal**: Create reproducible mermaid.live URL generation script to eliminate regeneration churn

**Independent Test**: Run `make regenerate-mermaid-url` and verify output URL renders correctly in browser with dark theme

### Implementation for User Story 4

- [x] T004 [US4] Create scripts/regenerate-mermaid-url.py with URL generation logic
- [x] T005 [US4] Add --validate-only flag for syntax validation in scripts/regenerate-mermaid-url.py
- [x] T006 [US4] Add regenerate-mermaid-url target in Makefile
- [x] T007 [US4] Test script with existing docs/diagrams/architecture.mmd

**Checkpoint**: URL generation script works and produces valid mermaid.live URLs

---

## Phase 3: User Story 1 - Developers View Accurate Architecture (Priority: P1)

**Goal**: README.md diagrams accurately show current architecture without CF, with Tiingo/Finnhub

**Independent Test**: View README.md in GitHub and verify diagrams render correctly with no CF node, showing Tiingo/Finnhub as data sources

### Implementation for User Story 1

- [x] T008 [US1] Remove CF node from README.md line 248 (Browser ==>|HTTPS| CF)
- [x] T009 [US1] Remove CF routing lines 250-252 in README.md (CF ==>|/static/*| Amplify, etc.)
- [x] T010 [US1] Add direct Browser connections in README.md: Browser ==>|Static| Amplify
- [x] T011 [US1] Add direct Browser connections in README.md: Browser ==>|/api/*| APIGW
- [x] T012 [US1] Add direct Browser connections in README.md: Browser ==>|/api/v2/stream*| SSELambda
- [x] T013 [US1] Update edgeStyle class line 314 in README.md to remove CF
- [x] T014 [US1] Verify README.md diagram still renders correctly (check mermaid syntax)

**Checkpoint**: README.md inline diagram shows correct architecture without CF

---

## Phase 4: User Story 3 - Architecture Diagrams Stay Synchronized (Priority: P3)

**Goal**: architecture.mmd and README.md show identical architecture; mermaid.live badge updated

**Independent Test**: Compare External subgraphs in both files and click mermaid.live badge to verify it matches

### Implementation for User Story 3

- [x] T015 [US3] Replace NewsAPI with Tiingo node in docs/diagrams/architecture.mmd External Services subgraph
- [x] T016 [US3] Add Finnhub node in docs/diagrams/architecture.mmd External Services subgraph
- [x] T017 [US3] Update OAuthProviders node formatting to match README.md style in docs/diagrams/architecture.mmd
- [x] T018 [US3] Run `make regenerate-mermaid-url` to generate new URL from architecture.mmd
- [x] T019 [US3] Update mermaid.live badge URL in README.md line 185 with generated URL
- [x] T020 [US3] Verify mermaid.live link renders correctly in browser

**Checkpoint**: architecture.mmd and README.md are synchronized; mermaid.live badge works

---

## Phase 5: User Story 2 - Onboarding Engineers Understand Data Flow (Priority: P2)

**Goal**: src/ documentation accurately describes Tiingo/Finnhub instead of NewsAPI

**Independent Test**: Read src/README.md and src/lambdas/ingestion/README.md - all data source references should be Tiingo/Finnhub

### Implementation for User Story 2

- [x] T021 [P] [US2] Update src/README.md line 8: "NewsAPI data ingestion" → "Tiingo + Finnhub financial news ingestion"
- [x] T022 [P] [US2] Update src/lambdas/ingestion/README.md line 5: Replace NewsAPI description with Tiingo/Finnhub
- [x] T023 [US2] Update src/lambdas/ingestion/README.md line 14: Update data flow diagram to show Tiingo/Finnhub
- [x] T024 [US2] Update src/lambdas/ingestion/README.md line 34: Update secrets reference from newsapi to tiingo/finnhub
- [x] T025 [US2] Update src/lambdas/ingestion/README.md lines 60-63: Replace NewsAPI adapter references with Tiingo/Finnhub adapters
- [x] T026 [US2] Update rate limits documentation: Tiingo (500 req/day), Finnhub (60 req/min)

**Checkpoint**: All src/ documentation shows Tiingo/Finnhub as data sources

---

## Phase 6: Polish & Verification

**Purpose**: Final verification and cleanup

- [x] T027 Run grep to verify zero "NewsAPI" matches in target files
- [x] T028 Run grep to verify zero "CF[" or "CloudFront" in README.md mermaid blocks
- [x] T029 Push branch and verify all diagrams render in GitHub preview
- [x] T030 Run `make validate` to ensure no linting issues (Python lint passed; TF modules not init'd - pre-existing)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **User Story 4 (Phase 2)**: Depends on Setup - Creates tooling needed for US3
- **User Story 1 (Phase 3)**: Depends on Setup - Can run parallel with US4
- **User Story 3 (Phase 4)**: Depends on US4 (needs script for URL generation)
- **User Story 2 (Phase 5)**: Depends on Setup - Independent of other stories
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 4 (Script)**: Independent - creates tooling
- **User Story 1 (README CF fix)**: Independent of other stories
- **User Story 3 (Diagram sync)**: Needs US4 script for URL regeneration
- **User Story 2 (src/ docs)**: Independent of other stories

### Parallel Opportunities

- US4 and US1 can run in parallel after Setup
- US2 can run in parallel with US1 and US4
- Within US2, T021 and T022 can run in parallel (different files)

---

## Parallel Example: User Story 2

```bash
# Launch parallel tasks (different files):
Task: "Update src/README.md line 8: NewsAPI → Tiingo + Finnhub"
Task: "Update src/lambdas/ingestion/README.md line 5: Replace NewsAPI description"
```

---

## Implementation Strategy

### MVP First (User Stories 4 + 1)

1. Complete Phase 1: Setup
2. Complete Phase 2: User Story 4 (Script) - enables reproducible URL generation
3. Complete Phase 3: User Story 1 (README CF fix) - fixes most visible issue
4. **STOP and VALIDATE**: Push and verify README renders correctly
5. Continue with US3 and US2

### Incremental Delivery

1. Setup complete → Ready to work
2. US4 complete → Script available for future use
3. US1 complete → README.md CF issue fixed → Validate in GitHub
4. US3 complete → architecture.mmd fixed, mermaid.live badge updated
5. US2 complete → src/ documentation updated
6. Polish → All verification complete

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- This is documentation-only feature - no code tests needed
- Verify diagrams render correctly in GitHub after push
- Use the regenerate-mermaid-url script for all future URL updates
