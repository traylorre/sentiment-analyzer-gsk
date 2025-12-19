# Feature Specification: Consolidate Status Field

**Feature Branch**: `503-consolidate-status-field`
**Created**: 2025-12-19
**Status**: Draft
**Input**: Consolidate is_active/is_enabled boolean attributes to single status string field across all entity types (CONFIGURATION, ALERT_RULE). Remove redundant boolean attributes. Update all write paths. Context: This fixes the GSI query mismatch where by_entity_status GSI expects status string but data has is_active boolean.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Active Configuration Query Performance (Priority: P1)

The system administrator needs the ingestion Lambda to efficiently query active user configurations without scanning the entire table. Currently, the `by_entity_status` GSI expects a `status` string attribute, but configuration data only has `is_active` boolean, causing the GSI query to return zero results.

**Why this priority**: This is a blocking production issue. The ingestion Lambda cannot find active configurations, meaning no articles are fetched for any users.

**Independent Test**: Can be fully tested by invoking the ingestion Lambda and verifying it returns active tickers from user configurations.

**Acceptance Scenarios**:

1. **Given** a user has an active configuration with tickers, **When** the ingestion Lambda queries for active configurations, **Then** the configuration is found via the `by_entity_status` GSI
2. **Given** a user has soft-deleted their configuration, **When** the ingestion Lambda queries for active configurations, **Then** the soft-deleted configuration is NOT returned
3. **Given** 100 configurations exist (50 active, 50 inactive), **When** querying via GSI, **Then** only 50 items are read (not 100 scanned then filtered)

---

### User Story 2 - Alert Rule Status Consistency (Priority: P2)

Alert rules use `is_enabled` boolean to toggle alert evaluation on/off. The notification service needs to query enabled alert rules efficiently via the GSI, using consistent `status` field semantics.

**Why this priority**: Alert evaluation works but uses FilterExpression on boolean instead of GSI range key, causing O(partition) instead of O(result) performance.

**Independent Test**: Can be fully tested by creating enabled/disabled alerts and verifying GSI queries return correct results.

**Acceptance Scenarios**:

1. **Given** an enabled alert rule exists, **When** querying `by_entity_status` with `status=enabled`, **Then** the alert rule is returned
2. **Given** a disabled alert rule exists, **When** querying `by_entity_status` with `status=enabled`, **Then** the alert rule is NOT returned
3. **Given** a user toggles an alert from enabled to disabled, **When** the update completes, **Then** the `status` field changes from "enabled" to "disabled"

---

### User Story 3 - Digest Settings Query (Priority: P3)

Digest settings use `enabled` boolean to toggle daily digest emails. The digest service needs to query enabled digest settings via GSI for scheduled processing.

**Why this priority**: Digest processing is a batch job that can tolerate slower queries, but consistency with other entity types simplifies code and mental model.

**Independent Test**: Can be fully tested by creating digest settings with various enabled states and verifying GSI queries.

**Acceptance Scenarios**:

1. **Given** a user has enabled digest settings, **When** the digest service queries for enabled digests, **Then** the settings are returned via GSI
2. **Given** a user has disabled digest settings, **When** the digest service queries, **Then** the settings are NOT returned

---

### Edge Cases

- What happens when migrating existing data that has `is_active=true` but no `status` field?
  - Migration must add `status="active"` to all items with `is_active=true` (or no `is_active` field)
  - Migration must add `status="inactive"` to all items with `is_active=false`
- What happens when reading old data that only has boolean field?
  - Read paths must handle both formats during transition: check `status` first, fall back to boolean
- What happens when code writes boolean but GSI expects string?
  - All write paths must be updated atomically with migration to prevent data inconsistency

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST store entity status as a string field named `status` with values: "active", "inactive", "enabled", "disabled"
- **FR-002**: System MUST remove redundant boolean fields (`is_active`, `is_enabled`, `enabled`) after migration
- **FR-003**: System MUST update all write paths to set `status` string instead of boolean fields
- **FR-004**: System MUST update all read paths to check `status` string instead of boolean fields
- **FR-005**: System MUST provide a data migration script to convert existing boolean fields to status strings
- **FR-006**: System MUST maintain backward compatibility during migration by supporting both formats temporarily

### Status Value Mapping

| Entity Type | Boolean Field | Boolean Value | Status String |
|-------------|---------------|---------------|---------------|
| CONFIGURATION | is_active | true | "active" |
| CONFIGURATION | is_active | false | "inactive" |
| ALERT_RULE | is_enabled | true | "enabled" |
| ALERT_RULE | is_enabled | false | "disabled" |
| DIGEST_SETTINGS | enabled | true | "enabled" |
| DIGEST_SETTINGS | enabled | false | "disabled" |

### Key Entities

- **CONFIGURATION**: User's ticker tracking configuration. Status indicates soft-delete state (active/inactive).
- **ALERT_RULE**: User's price alert rule. Status indicates feature toggle (enabled/disabled).
- **DIGEST_SETTINGS**: User's daily digest preferences. Status indicates feature toggle (enabled/disabled).
- **TICKER_INFO**: Reference data for stock tickers. NOT included in this migration (separate concern for delisting).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Ingestion Lambda successfully queries active configurations via GSI (currently returns 0, should return all active configs)
- **SC-002**: All entity reads use O(result) GSI queries instead of O(partition) filtered scans
- **SC-003**: Zero data inconsistency between boolean and string fields after migration (no items have mismatched values)
- **SC-004**: All existing functionality continues to work (toggle alerts, soft-delete configs, enable/disable digests)
- **SC-005**: No boolean status fields remain in codebase after migration complete

## Assumptions

1. The `by_entity_status` GSI is already deployed with `status` as the range key (confirmed in Terraform)
2. TICKER_INFO.is_active is out of scope (reference data, not user entity, different lifecycle)
3. Migration can be performed during low-traffic window
4. Existing items without explicit boolean field default to "active" or "enabled" based on entity type
5. The transition period where both formats are supported will be brief (single deployment)

## Out of Scope

- TICKER_INFO delisting status (separate reference data concern)
- Adding new status values beyond active/inactive/enabled/disabled
- Changing GSI structure (already correct)
- UI changes (backend-only data model change)
