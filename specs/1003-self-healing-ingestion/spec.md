# Feature Specification: Self-Healing Ingestion

**Feature Branch**: `1003-self-healing-ingestion`
**Created**: 2025-12-20
**Status**: Draft
**Input**: User description: "Self-healing ingestion: detect and republish stale pending items. Problem: 463 items in preprod-sentiment-items have status=pending but no sentiment field. They were ingested but never published to SNS because they were all duplicates of previously-seen articles. The Analysis Lambda never triggered. Solution: Modify ingestion Lambda to detect items stuck in pending for >1 hour and republish them to SNS topic preprod-sentiment-analysis-requests for reprocessing."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic Reprocessing of Stale Items (Priority: P1)

When articles are ingested but not processed due to duplicate detection or other transient issues, the system automatically detects these stale items and republishes them for analysis, ensuring no data is permanently stuck in a pending state.

**Why this priority**: This is the core functionality that solves the immediate problem of 463+ items stuck in pending status. Without this, the dashboard shows empty/stale data despite successful ingestion.

**Independent Test**: Can be fully tested by ingesting a test article, manually setting its status to pending for >1 hour, running ingestion, and verifying the item is republished to SNS and eventually analyzed.

**Acceptance Scenarios**:

1. **Given** an item exists in DynamoDB with status="pending" and no sentiment field for more than 1 hour, **When** the ingestion Lambda runs, **Then** the item is published to the analysis SNS topic for reprocessing
2. **Given** an item exists with status="pending" and no sentiment field for less than 1 hour, **When** the ingestion Lambda runs, **Then** the item is NOT republished (to avoid duplicate processing during normal pipeline latency)
3. **Given** an item exists with status="analyzed" and has a sentiment field, **When** the ingestion Lambda runs, **Then** the item is NOT republished (already processed)

---

### User Story 2 - Self-Healing Without Manual Intervention (Priority: P1)

Operations teams should not need to run manual scripts or trigger Lambda invocations to fix stuck items. The self-healing mechanism runs automatically as part of the regular ingestion schedule.

**Why this priority**: Reduces operational burden and ensures issues are automatically resolved without human intervention.

**Independent Test**: Can be tested by creating pending items, waiting for scheduled ingestion runs, and verifying items are automatically reprocessed without any manual action.

**Acceptance Scenarios**:

1. **Given** stale pending items exist in the database, **When** the scheduled ingestion Lambda runs (every 5 minutes), **Then** stale items are detected and republished without any manual intervention
2. **Given** no stale pending items exist, **When** the scheduled ingestion Lambda runs, **Then** normal ingestion proceeds with no additional overhead

---

### User Story 3 - Observability of Self-Healing Actions (Priority: P2)

Operations teams should be able to see when items are being reprocessed through self-healing, including counts and reasons.

**Why this priority**: Enables monitoring and debugging of pipeline health, but core functionality works without it.

**Independent Test**: Can be tested by checking CloudWatch logs after self-healing runs for expected metrics and log entries.

**Acceptance Scenarios**:

1. **Given** the ingestion Lambda republishes stale items, **When** viewing CloudWatch logs, **Then** a summary log entry shows the count of items republished (e.g., "Self-healing: republished 5 stale items to analysis queue")
2. **Given** no stale items were found, **When** viewing CloudWatch logs, **Then** a log entry confirms the check was performed (e.g., "Self-healing: 0 stale items found")

---

### Edge Cases

- What happens when there are more than 1000 stale items? System should batch republishing to avoid overwhelming SNS (batch size of 100).
- What happens if SNS publish fails for some items? System should log the failure and retry on next ingestion run.
- What happens if an item is republished but analysis fails again? Item remains in pending with updated timestamp; will be retried after another hour.
- What happens if ingestion Lambda times out during self-healing? Use a separate CloudWatch metric alarm to detect incomplete runs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST query DynamoDB for items with status="pending" that lack a sentiment field and have a timestamp older than 1 hour
- **FR-002**: System MUST publish matching items to the SNS topic used for analysis requests (preprod-sentiment-analysis-requests)
- **FR-003**: System MUST log the count of items republished for observability
- **FR-004**: System MUST batch republishing to avoid overwhelming SNS (maximum 100 items per batch)
- **FR-005**: System MUST NOT republish items that already have a sentiment field (already processed)
- **FR-006**: System MUST NOT republish items that have been pending for less than 1 hour (allow normal pipeline latency)
- **FR-007**: System MUST use a GSI query (by_status) for efficient retrieval of pending items
- **FR-008**: System MUST handle SNS publish failures gracefully by logging errors and continuing with remaining items

### Key Entities

- **SentimentItem**: Represents an article/news item. Key attributes: source_id (PK), status (pending/analyzed), sentiment (positive/neutral/negative), timestamp, text_for_analysis
- **Analysis Request**: Message published to SNS topic containing item identifiers for the Analysis Lambda to process

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All items in pending status for more than 1 hour are automatically republished within the next scheduled ingestion run (5 minutes)
- **SC-002**: Dashboard shows non-zero item counts within 10 minutes of self-healing detection for stale items
- **SC-003**: Zero manual intervention required to recover from stuck pending items
- **SC-004**: Self-healing check adds less than 5 seconds to normal ingestion execution time
- **SC-005**: 100% of republished items eventually reach analyzed status (may take multiple retry cycles for persistent failures)

## Assumptions

- The existing SNS subscription to the Analysis Lambda is correctly configured and active
- The Analysis Lambda successfully processes items when triggered via SNS
- DynamoDB has a GSI on status field (by_status) for efficient querying
- The stale threshold of 1 hour is appropriate for distinguishing between normal latency and stuck items
- The scheduled ingestion runs every 5 minutes via EventBridge
