# Feature Specification: Add GOOG Ticker Support

**Feature Branch**: `1116-add-goog-ticker`
**Created**: 2026-01-01
**Status**: Draft
**Input**: User description: "Add GOOG (Alphabet Class C) ticker to the ticker search database. Root cause: infrastructure/data/us-symbols.json only has GOOGL, not GOOG. Tiingo API supports both. Fix: Add GOOG entry to us-symbols.json with same format as GOOGL. Also verify ticker_cache.py loads both correctly. Files: infrastructure/data/us-symbols.json, src/lambdas/dashboard/tickers.py (hardcoded fallback list)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Search for GOOG Ticker (Priority: P1)

As a dashboard user, I want to search for "GOOG" and see Alphabet Class C shares in the search results, so that I can view OHLC price data for GOOG specifically (distinct from GOOGL Class A shares).

**Why this priority**: This is the core functionality - users expect GOOG to be searchable since it's a major US equity. Currently searching "GOOG" only returns GOOGL, which is confusing and incomplete.

**Independent Test**: Can be fully tested by entering "GOOG" in the ticker search and verifying it appears in results with correct company name "Alphabet Inc - Class C".

**Acceptance Scenarios**:

1. **Given** I am on the dashboard, **When** I search for "GOOG", **Then** I see "GOOG - Alphabet Inc - Class C" in the search results
2. **Given** I am on the dashboard, **When** I search for "GOOG", **Then** both GOOG and GOOGL appear as distinct options
3. **Given** I select GOOG from search results, **When** the chart loads, **Then** I see OHLC price data for GOOG (not GOOGL)

---

### User Story 2 - View GOOG Price Data (Priority: P1)

As a dashboard user, I want to view OHLC candlestick charts for GOOG at various time resolutions, so that I can analyze Alphabet Class C share price movements.

**Why this priority**: Tied with search - once searchable, users need to actually view the data. The backend already supports this (Tiingo returns GOOG data), but the ticker must be in the search database first.

**Independent Test**: After selecting GOOG, verify OHLC chart renders with correct price data matching external data source.

**Acceptance Scenarios**:

1. **Given** I have selected GOOG ticker, **When** the chart loads, **Then** I see candlestick data with correct OHLC values
2. **Given** I am viewing GOOG data, **When** I change resolution to 5-minute, **Then** the chart updates with intraday GOOG data
3. **Given** I am viewing GOOG data, **When** I check the ticker label, **Then** it displays "GOOG" (not GOOGL)

---

### Edge Cases

- What happens when user types "goog" (lowercase)? System normalizes to "GOOG" and matches correctly.
- What happens when user types "GOO"? System shows both GOOG and GOOGL as partial matches.
- How does system differentiate GOOG from GOOGL in search results? Display full company name with share class distinction.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST include GOOG in the ticker search database with metadata (symbol, name, exchange)
- **FR-002**: System MUST return GOOG as a distinct result when users search for "GOOG"
- **FR-003**: System MUST return both GOOG and GOOGL when users search for partial match "GOO"
- **FR-004**: System MUST display differentiated names: "Alphabet Inc - Class C" for GOOG vs "Alphabet Inc." for GOOGL
- **FR-005**: System MUST fetch OHLC data for GOOG ticker from price data provider
- **FR-006**: System MUST include GOOG in any hardcoded fallback ticker lists alongside GOOGL

### Key Entities

- **Ticker Symbol (GOOG)**: Represents Alphabet Inc Class C shares, traded on NASDAQ, distinct from GOOGL (Class A)
- **Ticker Metadata**: Symbol, company name, exchange code, active status

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users searching for "GOOG" see GOOG in results within 500ms (same as other tickers)
- **SC-002**: 100% of GOOG ticker queries return valid OHLC data
- **SC-003**: GOOG and GOOGL are correctly distinguished in all search results and chart displays
- **SC-004**: No regression in existing ticker search functionality for other symbols

## Assumptions

- External price data provider supports GOOG ticker (verified: returns valid metadata and price data)
- GOOG uses same data format as other NASDAQ tickers in the symbol database
- No additional rate limits apply specifically to GOOG
- Frontend search component handles new ticker without modification (data-driven)

## Out of Scope

- Adding other missing tickers (this spec focuses only on GOOG)
- Modifying the ticker search algorithm or ranking
- Adding GOOG to any watchlist defaults or featured tickers
- Historical data backfill beyond what price data provider offers
