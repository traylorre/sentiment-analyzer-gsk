# Feature Specification: Fix Ticker Search API Contract

**Feature Branch**: `1120-fix-ticker-search-contract`
**Created**: 2026-01-02
**Status**: Draft
**Input**: User description: "Fix ticker search API contract mismatch - frontend expects bare array from GET /api/v2/tickers/search but backend returns wrapped response with results field"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ticker Search Returns Results (Priority: P1)

A user searching for stock tickers in the dashboard search box types a query (e.g., "GOOG") and expects to see matching ticker symbols displayed as search results.

**Why this priority**: This is the core functionality - without working ticker search, users cannot select stocks to view on the dashboard. This blocks the primary demo goal of displaying OHLC charts.

**Independent Test**: Type "GOOG" in the ticker search box and verify that "GOOG - Alphabet Inc Class C" and "GOOGL - Alphabet Inc Class A" appear in the dropdown results.

**Acceptance Scenarios**:

1. **Given** user is on the dashboard, **When** user types "GOOG" in the ticker search box, **Then** matching tickers including GOOG and GOOGL are displayed in the dropdown
2. **Given** user is on the dashboard, **When** user types "Apple" in the ticker search box, **Then** AAPL appears in the dropdown with company name "Apple Inc"
3. **Given** user is on the dashboard, **When** user types a partial symbol like "MS", **Then** multiple matches (MSFT, MS) are displayed

---

### User Story 2 - Graceful Handling of No Results (Priority: P2)

When a user searches for a ticker that doesn't exist, the system should gracefully display "no results" rather than showing an error or crashing.

**Why this priority**: Important for user experience but not blocking core functionality.

**Independent Test**: Type "ZZZZZ" in the ticker search box and verify an appropriate "no results" message is shown.

**Acceptance Scenarios**:

1. **Given** user is on the dashboard, **When** user types a non-existent ticker like "ZZZZZ", **Then** a "no results found" message is displayed (not an error)

---

### Edge Cases

- What happens when the search query is empty? Should show no results, not an error.
- How does the system handle special characters in search? Input is sanitized by the backend.
- What happens if the backend is unreachable? Should show appropriate error message.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display ticker search results when user types in the search box
- **FR-002**: System MUST correctly parse the wrapped response from the backend ticker search endpoint
- **FR-003**: Users MUST see ticker symbol, company name, and exchange for each search result
- **FR-004**: System MUST display a "no results" message when search returns empty results
- **FR-005**: System MUST maintain backward compatibility - existing search functionality continues to work

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can search for "GOOG" and see results within 1 second
- **SC-002**: 100% of valid ticker searches return visible results in the dropdown
- **SC-003**: Zero console errors when performing ticker searches
- **SC-004**: Dashboard demo is unblocked - users can search and select tickers to view OHLC charts

## Assumptions

- Backend API contract is correct (returning `{results: [...]}` wrapper is RESTful best practice)
- Frontend code change is isolated to the API client layer
- No backend changes required for this fix

## Out of Scope

- Backend API modifications
- Changes to the ticker validation endpoint
- Performance optimizations for search
