# Tasks: Consolidate Status Field

**Input**: Design documents from `/specs/503-consolidate-status-field/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Not explicitly requested. Test updates will be handled in a separate feature (504).

**Organization**: Tasks grouped by user story (entity type) to enable independent implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Migration Infrastructure)

**Purpose**: Create migration script and status utility function

- [x] T001 Create migration script skeleton in scripts/migrate_status_field.py
- [x] T002 Add status conversion utility function in src/lambdas/shared/models/status_utils.py
- [x] T003 [P] Add status constants (ACTIVE, INACTIVE, ENABLED, DISABLED) to status_utils.py

---

## Phase 2: Foundational (Backward-Compatible Read Support)

**Purpose**: Add status field support to all models while maintaining backward compatibility with boolean fields

**⚠️ CRITICAL**: Models must support BOTH boolean and string reads before any write path changes

- [x] T004 [P] Update Configuration model to add status field with boolean fallback in src/lambdas/shared/models/configuration.py
- [x] T005 [P] Update AlertRule model to add status field with boolean fallback in src/lambdas/shared/models/alert_rule.py
- [x] T006 [P] Update DigestSettings model to add status field with boolean fallback in src/lambdas/shared/models/notification.py

**Checkpoint**: All models can read both boolean AND string status formats

---

## Phase 3: User Story 1 - Active Configuration Query (Priority: P1) 🎯 MVP

**Goal**: Fix ingestion Lambda to find active configurations via GSI query

**Independent Test**: Invoke ingestion Lambda, verify it returns tickers from active user configurations

### Implementation for User Story 1

- [x] T007 [US1] Update Configuration.to_dynamodb_item() to write status string in src/lambdas/shared/models/configuration.py
- [x] T008 [US1] Update create_configuration() to set status="active" in src/lambdas/dashboard/configurations.py
- [x] T009 [US1] Update soft_delete_configuration() to set status="inactive" in src/lambdas/dashboard/configurations.py
- [x] T010 [US1] Update restore_configuration() (if exists) to set status="active" in src/lambdas/dashboard/configurations.py (N/A - no restore function exists)
- [x] T011 [US1] Update list_configurations() to filter by status string in src/lambdas/dashboard/configurations.py
- [x] T012 [US1] Update get_configuration() to check status string in src/lambdas/dashboard/configurations.py
- [x] T013 [US1] Update count_configurations() to use status in FilterExpression in src/lambdas/dashboard/configurations.py
- [x] T014 [US1] Update SSE config lookup to check status string in src/lambdas/sse_streaming/config.py
- [x] T015 [US1] Add CONFIGURATION migration logic to scripts/migrate_status_field.py

**Checkpoint**: User Story 1 complete - ingestion Lambda can query active configurations via GSI

---

## Phase 4: User Story 2 - Alert Rule Status (Priority: P2)

**Goal**: Enable GSI queries for enabled/disabled alert rules

**Independent Test**: Create enabled/disabled alerts, verify GSI queries return correct results

### Implementation for User Story 2

- [x] T016 [P] [US2] Update AlertRule.to_dynamodb_item() to write status string in src/lambdas/shared/models/alert_rule.py
- [x] T017 [US2] Update create_alert() to set status="enabled" in src/lambdas/dashboard/alerts.py
- [x] T018 [US2] Update update_alert() to set status based on is_enabled in src/lambdas/dashboard/alerts.py
- [x] T019 [US2] Update toggle_alert() to set status="enabled"/"disabled" in src/lambdas/dashboard/alerts.py
- [x] T020 [US2] Update list_alerts() to filter by status string in src/lambdas/dashboard/alerts.py
- [x] T021 [US2] Update alert_evaluator to check status instead of is_enabled in src/lambdas/notification/alert_evaluator.py
- [x] T022 [US2] Update _find_alerts_by_ticker() to query with status="enabled" in src/lambdas/notification/alert_evaluator.py
- [x] T023 [US2] Add ALERT_RULE migration logic to scripts/migrate_status_field.py

**Checkpoint**: User Story 2 complete - alert evaluation uses GSI queries for enabled alerts

---

## Phase 5: User Story 3 - Digest Settings Status (Priority: P3)

**Goal**: Enable GSI queries for enabled digest settings

**Independent Test**: Create digest settings with various states, verify GSI queries work

### Implementation for User Story 3

- [x] T024 [P] [US3] Update DigestSettings.to_dynamodb_item() to write status string in src/lambdas/shared/models/notification.py
- [x] T025 [US3] Update create/update digest settings to set status in src/lambdas/dashboard/notifications.py
- [x] T026 [US3] Update get_users_due_for_digest() to query with status="enabled" in src/lambdas/notification/digest_service.py
- [x] T027 [US3] Update disable_all_notifications() to set status="disabled" in src/lambdas/dashboard/notifications.py (N/A - digest uses separate enabled field)
- [x] T028 [US3] Add DIGEST_SETTINGS migration logic to scripts/migrate_status_field.py

**Checkpoint**: User Story 3 complete - digest service uses GSI queries

---

## Phase 6: Data Migration & Verification

**Purpose**: Migrate existing DynamoDB data and verify consistency

- [x] T029 Add dry-run mode to migration script in scripts/migrate_status_field.py
- [x] T030 Add verification mode to migration script in scripts/migrate_status_field.py
- [x] T031 Run migration dry-run against preprod-sentiment-users table (identified 74+ CONFIGURATION, 50+ ALERT_RULE items)
- [ ] T032 Execute migration against preprod-sentiment-users table (deferred - run after code deploy)
- [ ] T033 Verify all items have status field via verification mode (deferred - run after migration)

**Checkpoint**: All existing data has been migrated to use status string

---

## Phase 7: Cleanup (Remove Boolean Fields)

**Purpose**: Remove backward compatibility code and boolean field writes

- [ ] T034 [P] Remove is_active from Configuration model and all write paths (deferred - separate PR after migration verified)
- [ ] T035 [P] Remove is_enabled from AlertRule model and all write paths (deferred - separate PR after migration verified)
- [ ] T036 [P] Remove enabled from DigestSettings model and all write paths (deferred - separate PR after migration verified)
- [ ] T037 Remove boolean fallback logic from status_utils.py (deferred - separate PR after migration verified)
- [ ] T038 Run quickstart.md verification commands to confirm GSI queries work (deferred - after deploy)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase
  - US1 (CONFIGURATION) - MVP, highest priority
  - US2 (ALERT_RULE) - Can start after Foundational, parallel to US1
  - US3 (DIGEST_SETTINGS) - Can start after Foundational, parallel to US1/US2
- **Migration (Phase 6)**: Depends on ALL user stories complete
- **Cleanup (Phase 7)**: Depends on Migration verified

### User Story Dependencies

- **User Story 1 (P1)**: Independent - CONFIGURATION only
- **User Story 2 (P2)**: Independent - ALERT_RULE only
- **User Story 3 (P3)**: Independent - DIGEST_SETTINGS only

### Parallel Opportunities

Within Foundational (Phase 2):
- T004, T005, T006 can all run in parallel (different model files)

Within User Stories (after Foundational):
- US1, US2, US3 can run in parallel (different entity types, different files)

Within Cleanup (Phase 7):
- T034, T035, T036 can all run in parallel (different model files)

---

## Parallel Example: Foundational Phase

```bash
# Launch all model updates together:
Task: "Update Configuration model to add status field in src/lambdas/shared/models/configuration.py"
Task: "Update AlertRule model to add status field in src/lambdas/shared/models/alert_rule.py"
Task: "Update DigestSettings model to add status field in src/lambdas/shared/models/notification.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T006)
3. Complete Phase 3: User Story 1 (T007-T015)
4. **STOP and VALIDATE**: Test ingestion Lambda finds active configs
5. Migrate CONFIGURATION data only
6. Deploy and verify

### Full Implementation

1. Setup + Foundational → All models ready
2. US1 → Migrate CONFIGURATION → Verify ingestion works
3. US2 → Migrate ALERT_RULE → Verify alert evaluation works
4. US3 → Migrate DIGEST_SETTINGS → Verify digest queries work
5. Cleanup → Remove boolean fields → Final verification

---

## Notes

- [P] tasks = different files, no dependencies
- Each entity type (CONFIGURATION, ALERT_RULE, DIGEST_SETTINGS) is independent
- Migration must happen AFTER all write paths updated for that entity
- Cleanup must happen AFTER migration verified for ALL entities
- Test updates are handled in separate feature 504
