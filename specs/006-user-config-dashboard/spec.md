# Feature Specification: Financial News Sentiment & Asset Volatility Dashboard

**Feature Branch**: `006-user-config-dashboard`
**Created**: 2025-11-25
**Status**: Specification Complete (Ready for Planning)
**Input**: A serverless pipeline that ingests financial news to correlate media sentiment with asset volatility. Users specify stock tickers/sectors, observe sentiment trends from Tiingo AND Finnhub (compared side-by-side). Results persisted for returning users. Email notifications with configurable trending thresholds. Mobile-first, beautiful, responsive. Users can save multiple configurations (up to 2) with independent views.

## Pivot Notice

**2025-11-25**: Major redesign from general news (NewsAPI/Guardian) to financial news APIs (Tiingo + Finnhub) due to privacy law compliance requirements. All references to NewsAPI and The Guardian API have been purged. Hard cutover - no parallel operation with legacy sources.

## Data Sources

### Primary: Tiingo News API
- **Free Tier**: 500 symbol lookups/month, 50 symbols/hour for EOD data
- **News**: Curated financial news with topic tags and ticker associations
- **Price Data**: OHLC data for ATR calculation (decades of history)
- **Archive**: Historical data spans decades for backtesting
- **Production**: Allowed on free tier
- **Docs**: [Tiingo Pricing](https://www.tiingo.com/about/pricing)

### Secondary: Finnhub API
- **Free Tier**: 60 API calls/minute, 1 year historical data
- **News Sentiment**: Built-in sentiment scores per company (news-sentiment endpoint)
- **Price Data**: Real-time quotes, OHLC for ATR calculation
- **Coverage**: 60+ stock exchanges, real-time quotes, company fundamentals
- **Production**: Allowed on free tier
- **Docs**: [Finnhub Rate Limits](https://finnhub.io/docs/api/rate-limit)

### Comparison Strategy
Both APIs will be queried for the same tickers. The dashboard displays:
- Side-by-side sentiment comparison (Tiingo news via our model vs Finnhub built-in sentiment)
- Future: Accept Finnhub's sentiment directly for comparison
- Correlation analysis between sentiment and price volatility (ATR)
- Source attribution for each data point
- Quota management via aggressive deduplication + caching across users

## Clarifications

### Session 2025-11-25 (Round 1 - Foundation)

- Q: How long should anonymous user server-side data be retained? → A: Browser-only storage for anonymous users (no server-side), prompt to upgrade on first visit
- Q: How long should magic links remain valid? → A: 1-hour expiry
- Q: How should the system behave when data sources are unavailable? → A: Show cached/stale data with "last updated X ago" indicator
- Q: What level of observability is required? → A: Full observability: logs + metrics + distributed tracing (AWS X-Ray)
- Q: How long should authenticated sessions remain valid? → A: 30-day session, refreshed on activity

### Session 2025-11-25 (Round 2 - Data Source Pivot)

- Q: News source selection? → A: Pivot to financial news APIs (Tiingo + Finnhub) for privacy compliance
- Q: Date range handling? → A: Match API limitations (Tiingo decades, Finnhub 1 year on free tier)
- Q: Distributed tracing approach? → A: AWS X-Ray native with SNS message attribute propagation
- Q: Trace scope? → A: All 4 Lambdas (comprehensive coverage)
- Q: X-Ray IAM policy? → A: Use AWS managed policy AWSXRayDaemonWriteAccess
- Q: Email service? → A: SendGrid free tier (100 emails/day) with API key in AWS Secrets Manager
- Q: Auth provider? → A: AWS Cognito for Google/GitHub OAuth
- Q: Magic link email? → A: Custom Lambda + SendGrid (not Cognito built-in)
- Q: API resilience? → A: Aggressive caching (1hr TTL) + exponential backoff + circuit breaker (5 failures in 5 min = open, 60s recovery)

### Session 2025-11-25 (Round 3 - Financial Domain)

- Q: How should volatility be calculated? → A: ATR (Average True Range) using OHLC data
- Q: Price data source for ATR? → A: Both Tiingo and Finnhub for redundancy
- Q: Sentiment source approach? → A: Compare multiple sources - our model on news text vs Finnhub built-in sentiment (future: accept Finnhub score directly)
- Q: Tiingo quota strategy (500 symbols/month)? → A: Aggressive deduplication + caching across users tracking same tickers
- Q: Score display format? → A: Numeric with color gradient (red→yellow→green spectrum, -1 to +1)

### Session 2025-11-25 (Round 4 - Visualization & UX)

- Q: Divergence visualization? → A: Heat map matrix (Tickers x Sources)
- Q: Heat map dimensions? → A: Both views with user toggle (Tickers x Sources AND Tickers x Time Periods)
- Q: International ticker support? → A: US markets only for MVP (NYSE, NASDAQ, AMEX)
- Q: Ticker validation/autocomplete? → A: Hybrid with local cache (static ~8K symbols + API validation)

### Session 2025-11-25 (Round 5 - Anonymous Users & Refresh)

- Q: Anonymous storage location? → A: Browser localStorage only (no server-side for anonymous)
- Q: Data loss handling? → A: Show "upgrade to save permanently" prompt on first visit (proactive)
- Q: Real-time updates? → A: Periodic refresh (5 min) with countdown timer + manual refresh button
- Q: Correlation statistic? → A: Simple trend arrows initially, rolling correlation chart as future enhancement

### Session 2025-11-25 (Round 6 - Migration & Infrastructure)

- Q: NewsAPI migration approach? → A: Hard cutover to Tiingo/Finnhub (remove NewsAPI entirely)

### Session 2025-11-25 (Round 7 - Edge Cases)

- Q: Ticker delisting/symbol changes? → A: Alert user, keep historical data with old symbol
- Q: Circuit breaker threshold? → A: 5 failures in 5 minutes = open, 60s recovery before retry
- Q: Market hours for ATR? → A: Both regular and extended hours with user toggle
- Q: Dual API failure? → A: Show cached data with prominent "All sources unavailable" warning banner

---

## Audit Clarifications (Spec Review 2025-11-25)

### Audit Round 1 - Critical Conflicts

- Q: What happens to Features 001-005 (NewsAPI-based)? → A: DEPRECATE - Feature 006 is the production system; create legacy/v1 branch then remove old specs from main
- Q: How to handle 43+ files with stale NewsAPI references? → A: Batch update NOW before /speckit.plan; create minimal CHANGELOG.md noting breaking changes
- Q: X-Ray tracing conflict (Phase 2 deferred vs Day 1 mandatory)? → A: Update SECURITY_REVIEW.md - X-Ray is now Day 1 mandatory requirement
- Q: Credential rotation for new APIs (Tiingo/Finnhub/SendGrid)? → A: Add Tiingo + Finnhub to rotation schedule; SendGrid and Cognito are managed services (no manual rotation)

### Audit Round 2 - Cost & Attack Surface

- Q: Monthly cost budget for $100 target? → A: Aggressive caching strategy required; alert if daily burn rate exceeds $3.33 (1/30th of budget)
- Q: Credit exhaustion attack mitigation? → A: IP-based rate limiting + CAPTCHA on repeated anonymous config creation
- Q: Email abuse protection (SendGrid 100/day)? → A: All protections: verified sender, rate limiting, spam filtering + 50% quota alert
- Q: Anonymous user observability? → A: Pure client-side tracking only (no server-side anonymous session tracking)

### Audit Round 3 - Authentication & User Flows

- Q: Sign-out scope (all devices vs current)? → A: Current device only - simpler, faster, respects user intent
- Q: Magic link invalidation on new request? → A: Yes, invalidate old link + send notification email about invalidation
- Q: Token storage mechanism? → A: localStorage (persistent across browser sessions, not sessionStorage)
- Q: Account linking (email + OAuth same address)? → A: Require explicit user confirmation before merging accounts

### Audit Round 4 - Documentation & Chaos Testing

- Q: Documentation update strategy for 43+ files? → A: Batch update now - create clean baseline before planning
- Q: Chaos testing scenarios (replacing NewsAPI tests)? → A: Direct port to Tiingo/Finnhub - same failure patterns (timeout, 429, 500)
- Q: Ticker validation error UX? → A: Inline field errors (red border + error text below input)
- Q: Data retention policy? → A: 90 days for authenticated users; 30 days for anonymous (localStorage cleared anyway)

### Audit Round 5 - Market Hours & Delisting

- Q: Market closed periods (weekends/holidays)? → A: Predictive estimates using Finnhub pre-market quotes
- Q: Delisted ticker handling? → A: Auto-replace with successor ticker (e.g., TWTR→X) + simple toast notification
- Q: API quota prioritization under load? → A: Smart allocation - volatility-aware (high-volatility tickers get more frequent updates)
- Q: Migration guide for existing deployments? → A: Minimal CHANGELOG only - Features 001-005 never deployed to production

### Audit Round 6 - Futures & History

- Q: Pre-market data source for predictive estimates? → A: Finnhub pre-market quotes (no additional API cost)
- Q: Smart allocation quota balancing algorithm? → A: Volatility-aware - high-volatility tickers refresh more frequently, stable tickers use cached data longer
- Q: Ticker successor notification format? → A: Simple toast - "TWTR replaced with X (Twitter rebrand)" - auto-dismiss 5 seconds
- Q: Historical data access (90-day retention)? → A: UI-only charts - no programmatic API access to historical data

### Audit Round 7 - Security & Cost Final

- Q: Cost alerting thresholds? → A: Daily burn rate - alert if daily spend exceeds $3.33 (catches anomalies faster than monthly thresholds)
- Q: Security findings tracking? → A: Private repo only (../sentiment-analysis-gsk-security); public repo gets sanitized summary
- Q: Git history preservation for old specs? → A: Branch archive - create legacy/v1 branch, then remove from main
- Q: Additional dependencies identified? → A: Yes - analytics (CloudWatch RUM), error monitoring (Lambda Powertools), CDN (CloudFront + S3)

### Audit Round 8 - New Dependencies (MVP-Critical)

- Q: Analytics/tracking solution? → A: CloudWatch RUM (~$0.10 per 1K sessions) - native AWS integration
- Q: Error monitoring solution? → A: AWS Lambda Powertools (enhanced logging/tracing built into Lambda) - no extra service
- Q: CDN/caching strategy? → A: CloudFront + S3 (~$0.085/GB transfer) for dashboard static assets
- Q: MVP scope for new dependencies? → A: ALL MVP-critical - full observability from day 1

## User Roles

See [roles.md](./roles.md) for detailed role matrix and use-cases.

### Role Summary

| Role | Access Level | MVP | Notes |
|------|-------------|-----|-------|
| Anonymous User | Read-only preview (blurred heatmap) | Yes | 30-day localStorage session |
| Known User | Full features (2 configs) | Yes | Premium tier for expansion |
| Contributor | Community templates + ticker additions | Yes | Invite-only |
| Operator/On-Call | System management | Yes | Circuit breakers, cache, alerts |
| Admin | Full system access | Yes | Impersonation, bulk ops, flags |
| API Consumer | Programmatic access | Future | No external API for MVP |
| Auditor/Compliance | Audit trail access | Future | When PII compliance needed |
| Data Steward | Ticker management | Future | When cache mgmt complex |

### Role Transitions

All elevated roles (Contributor, Operator, Admin) are **invite-only** from existing role holders.

### Session 2025-11-27 (Round 17 - Role Audit)

- Q: Anonymous user preview content? → A: Heatmap teaser with blurred tickers, colors visible
- Q: Anonymous session expiry handling? → A: Cookie restore - same browser restores preferences
- Q: Known user comparison features? → A: All four (cross-config, historical replay, correlation matrix, sector benchmark)
- Q: Known user history granularity? → A: Adaptive (hourly <7d, daily >7d, weekly >30d)
- Q: Config limit expansion? → A: Premium tier unlocks 5+ configs (future monetization)
- Q: Contributor template sharing? → A: Public gallery with browse/filter/one-click import
- Q: Contributor ticker suggestions? → A: Direct add for trusted contributors (audit logged)
- Q: Operator circuit breaker controls? → A: Confirm dialog safeguard (not two-person rule)
- Q: Operator alert suppression? → A: Per user opt-in (users can opt-out for critical alerts)
- Q: Operator user config access? → A: Full access with audit log + justification required
- Q: Admin user impersonation? → A: Yes, audit logged
- Q: Admin feature flags? → A: Percentage rollout (gradual enablement)
- Q: Admin alert debugging? → A: Full toolkit (impersonate + simulator + delivery trace)
- Q: Notification channels? → A: Email + browser push for all alerts
- Q: Account deletion? → A: Soft delete with 90-day recovery window
- Q: Dual failure handling? → A: Show stale data with timestamp badge
- Q: Price data for correlation? → A: Both merged (Finnhub intraday, Tiingo historical)
- Q: Sector benchmark? → A: GICS standard (11 sectors)
- Q: Audit retention? → A: 90 days CloudWatch (standard)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Instant Anonymous Access (Priority: P1)

A potential employer visits the financial sentiment dashboard for the first time. Without any signup friction, they immediately see a clean onboarding flow where they can specify up to 5 stock tickers (e.g., "AAPL", "TSLA", "NVDA", "MSFT", "GOOGL") and select a timeframe (e.g., "last 7 days"). Within seconds, they see sentiment analysis results from BOTH Tiingo and Finnhub visualized in beautiful, responsive charts optimized for mobile, with correlation to price volatility (ATR). They also see a prompt encouraging them to create an account to save their work permanently.

**Why this priority**: This is the core value proposition - zero friction to experience the product. A potential employer can evaluate the system's capabilities in under 60 seconds without creating an account.

**Independent Test**: Can be fully tested by visiting the site on a mobile device, entering 5 tickers and a timeframe, and seeing dual-source sentiment charts render with volatility correlation.

**Acceptance Scenarios**:

1. **Given** a new visitor on mobile, **When** they land on the dashboard, **Then** they see a clean ticker input interface without any login prompts blocking access, PLUS a non-intrusive "upgrade to save" prompt
2. **Given** a user enters 5 tickers and selects "last 7 days", **When** they submit, **Then** sentiment results from both Tiingo AND Finnhub display within 10 seconds
3. **Given** results are displayed, **When** user rotates device or resizes browser, **Then** charts reflow responsively without data loss
4. **Given** a user has not provided email, **When** they close browser and return on same device, **Then** their previous configuration and results are restored via browser localStorage
5. **Given** results are displayed, **When** user views charts, **Then** they see:
   - Heat map matrix comparing sentiment across sources
   - ATR volatility correlation with trend arrows
   - Numeric scores (-1 to +1) with color gradient (red→yellow→green)
   - "Last updated X ago" with countdown to next refresh

---

### User Story 2 - Persist Identity & Cross-Device Access (Priority: P2)

After exploring the dashboard anonymously, the user decides they want to access their data from another device or ensure it's not lost. They can optionally upgrade their anonymous session by providing an email (magic link via SendGrid) or using social login (Google/GitHub via AWS Cognito). Once authenticated, all their configurations and historical data are permanently associated with their account.

**Why this priority**: Builds on P1 by adding persistence. Users who find value in P1 naturally want to preserve their work. This converts anonymous users to identified users.

**Independent Test**: Can be tested by creating anonymous config, then authenticating via email or social login, and verifying data persists across devices/browsers.

**Acceptance Scenarios**:

1. **Given** an anonymous user with saved configuration, **When** they click "Save permanently" and enter email, **Then** they receive a magic link via SendGrid within 60 seconds
2. **Given** user clicks magic link, **When** link is valid (within 1 hour), **Then** anonymous data merges with new account and user sees their configuration
3. **Given** user chooses "Sign in with Google", **When** OAuth completes via Cognito, **Then** anonymous data associates with Google identity
4. **Given** authenticated user on Device A, **When** they sign in on Device B, **Then** they see all their saved configurations and historical results
5. **Given** user's localStorage is cleared, **When** they return to dashboard, **Then** they see "Sign in to restore your saved configurations" prompt

---

### User Story 3 - Dual Configuration Comparison (Priority: P3)

A user wants to track two different portfolios or sectors simultaneously - for example, "Tech Giants" (AAPL, MSFT, GOOGL, NVDA, META) and "EV/Clean Energy" (TSLA, RIVN, LCID, ENPH, FSLR). They create their first configuration with 5 tech tickers and a 30-day timeframe. While that runs, they create a second configuration with 5 EV tickers and a 14-day timeframe. Both configurations query Tiingo AND Finnhub, and the user can switch between views to compare sentiment-volatility correlations across their two portfolios using the heat map matrix.

**Why this priority**: Power feature for engaged users. Demonstrates advanced capability and stickiness. Requires P1 foundation to be valuable.

**Independent Test**: Can be tested by creating Config A (5 tech tickers, 30 days), then Config B (5 EV tickers, 14 days), and verifying both appear in a configuration switcher with independent chart views.

**Acceptance Scenarios**:

1. **Given** user has one saved configuration, **When** they click "Add new configuration", **Then** they can specify a new set of up to 5 tickers and independent timeframe
2. **Given** user has two configurations, **When** they view the dashboard, **Then** they see a configuration switcher (tabs/dropdown) to toggle between views
3. **Given** user switches from Config A to Config B, **When** switch completes, **Then** charts update to show Config B's tickers and timeframe data
4. **Given** user has two configurations with different timeframes, **When** viewing each, **Then** the date range displayed matches each configuration's setting
5. **Given** user attempts to create a third configuration, **When** they click "Add new", **Then** they see a message indicating maximum of 2 configurations allowed
6. **Given** user toggles heat map view, **When** switching between "Sources" and "Time Periods" views, **Then** the matrix updates accordingly

---

### User Story 4 - Volatility & Sentiment Alerts (Priority: P4)

A user wants to be notified when stocks they're tracking experience significant sentiment shifts or volatility spikes. They configure notification rules - either based on sentiment score changes (e.g., "notify me when TSLA sentiment drops below -0.5") or volatility thresholds (e.g., "notify me when NVDA ATR exceeds 5%"). When thresholds are met, they receive email notifications via SendGrid.

**Why this priority**: Retention and engagement feature. Keeps users returning even when not actively using the dashboard. Requires P2 (email/identity) to deliver notifications.

**Independent Test**: Can be tested by setting a low threshold, waiting for trigger, and verifying email delivery with relevant summary.

**Acceptance Scenarios**:

1. **Given** authenticated user, **When** they view a configuration, **Then** they see option to "Set up alerts" for each ticker
2. **Given** user sets sentiment threshold of -0.3 for "AAPL", **When** Finnhub or Tiingo sentiment drops below -0.3, **Then** user receives email within 15 minutes
3. **Given** user sets volatility alert of 3% ATR for "TSLA", **When** ATR exceeds 3%, **Then** user receives email describing the spike
4. **Given** user receives notification email, **When** they click the link, **Then** they land on the relevant configuration view showing the triggering data
5. **Given** user wants to stop notifications, **When** they toggle off alerts for a ticker, **Then** no further emails are sent for that rule

---

### User Story 5 - Community Contributor (Priority: P5)

A power user who has been actively using the dashboard gets invited to become a Contributor. They can now create and share alert template bundles (e.g., "Earnings Season Tech Alerts") in a public gallery. Other users browse the gallery, filter by ticker or alert type, and import templates with one click. The Contributor can also directly add new tickers to the US symbols cache when users report missing symbols.

**Why this priority**: Community engagement feature. Reduces support burden and creates network effects as users share valuable configurations.

**Independent Test**: Can be tested by having a Contributor create a template, share it to the gallery, and verifying another user can find and import it with one click.

**Acceptance Scenarios**:

1. **Given** a Known User, **When** they receive Contributor invitation from existing Contributor or Admin, **Then** they can accept and gain Contributor role
2. **Given** a Contributor, **When** they create an alert template bundle, **Then** they can share it to the public gallery with name, description, and tags
3. **Given** any Known User, **When** they browse the template gallery, **Then** they can filter by ticker, alert type, and see import counts
4. **Given** a user finds a template, **When** they click "Import", **Then** the template's alert rules are added to their configuration in one click
5. **Given** a Contributor, **When** a user reports a missing ticker (e.g., "PLTR"), **Then** the Contributor can directly add it to the symbols cache (audit logged)

---

### User Story 6 - Operator Incident Response (Priority: P6)

An on-call engineer receives an alert that Tiingo API is returning 429 rate limit errors. They access the operator dashboard, view the circuit breaker status (currently half-open), and manually open it with a confirm dialog to prevent further requests. They check the quota dashboard showing 80% usage and pause non-critical background jobs. Before a scheduled maintenance window, they suppress alerts system-wide, but premium users who opted out still receive their critical alerts.

**Why this priority**: Operational resilience. Enables self-service incident response without code deployments.

**Independent Test**: Can be tested by simulating a rate limit scenario and verifying the operator can open circuit breaker and suppress alerts.

**Acceptance Scenarios**:

1. **Given** an Operator, **When** they view the operator dashboard, **Then** they see circuit breaker status for Tiingo, Finnhub, and SendGrid
2. **Given** an Operator, **When** they click "Open Circuit Breaker" for Tiingo, **Then** they see a confirm dialog before the state changes
3. **Given** an Operator, **When** they view quota dashboard, **Then** they see real-time API quota usage with ability to pause non-critical operations
4. **Given** an Operator, **When** they enable system-wide alert suppression, **Then** most users stop receiving alerts
5. **Given** a Premium User who opted out of suppression, **When** alert suppression is active, **Then** they still receive their critical alerts
6. **Given** an Operator debugging a user issue, **When** they view user's config, **Then** the access is audit logged with justification required

---

### User Story 7 - Admin User Management & Debugging (Priority: P7)

An admin receives a support request that a user's alerts never fire. The admin impersonates the user (audit logged) to see exactly what they see. They run the alert simulator in dry-run mode, which shows the alert threshold is set incorrectly. They trace the delivery path showing evaluation passed but SendGrid rejected due to invalid email. The admin also manages a gradual rollout of the new "overlay comparison" feature to 10% of users, then 50%, then 100%.

**Why this priority**: Platform management and quality assurance. Enables efficient debugging and controlled feature releases.

**Independent Test**: Can be tested by impersonating a user, running alert simulator, and verifying feature flag percentage rollout.

**Acceptance Scenarios**:

1. **Given** an Admin, **When** they select a user and click "Impersonate", **Then** they see the dashboard exactly as that user sees it (audit logged)
2. **Given** an Admin impersonating a user, **When** they click "Alert Simulator", **Then** they see a dry-run showing what would trigger
3. **Given** an Admin, **When** they click "Delivery Trace" for a notification, **Then** they see: evaluation result → SNS → Lambda → SendGrid → delivery status
4. **Given** an Admin, **When** they create a feature flag for "overlay-comparison", **Then** they can set it to percentage rollout (10%, then 50%, then 100%)
5. **Given** an Admin, **When** they view usage analytics, **Then** they see DAU, alert trigger rates, popular tickers, and error rates
6. **Given** an Admin, **When** they perform bulk operations (delete inactive users, reset quotas), **Then** changes are applied with audit trail

---

### Edge Cases

- **Invalid ticker**: Inline field validation with red border + error text below input (not toast/modal)
- **Both APIs return no data**: Display friendly "No data available for [TICKER]" message
- **Browser localStorage cleared**: Prompt "Sign in to restore your saved configurations"
- **Rate limits hit**: Circuit breaker trips (5 failures/5 min), show "last updated X ago" staleness indicator, 60s recovery
- **Email delivery fails**: Retry 3x over 1 hour via SendGrid, mark notification as failed with in-app indicator
- **Notification flood**: Rate limit to max 10 emails/day/user with digest option
- **Tiingo/Finnhub divergence**: Display both in heat map matrix, divergence visually apparent
- **Ticker delisted/merged**: Auto-replace with successor ticker (e.g., TWTR→X) + simple toast "TWTR replaced with X (Twitter rebrand)" auto-dismiss 5s
- **Both Tiingo AND Finnhub down**: Show cached data with prominent "All sources unavailable" banner
- **Extended hours toggle**: User can include/exclude pre/post-market data for ATR calculation
- **Market closed (weekends/holidays)**: Show predictive estimates using Finnhub pre-market quotes
- **Quota exhaustion approaching**: Smart allocation - volatility-aware prioritization (high-volatility tickers refresh more frequently)
- **Cost anomaly**: Alert if daily spend exceeds $3.33 (1/30th of $100 budget)
- **Magic link re-request**: Invalidate previous link + send notification about invalidation
- **Account linking conflict**: Require explicit user confirmation before merging email + OAuth accounts

## Requirements *(mandatory)*

### Functional Requirements

**Identity & Access**
- **FR-001**: System MUST allow immediate anonymous access without requiring signup
- **FR-002**: Anonymous user data MUST be stored in browser localStorage only; system MUST show "upgrade to save permanently" prompt on first visit
- **FR-003**: System MUST allow anonymous users to upgrade via email magic link (1-hour expiry) sent via custom Lambda + SendGrid
- **FR-004**: System MUST allow anonymous users to upgrade via social login (Google, GitHub) using AWS Cognito
- **FR-005**: System MUST merge localStorage data into authenticated account upon upgrade
- **FR-006**: System MUST allow authenticated users to access their data from any device
- **FR-006a**: Authenticated sessions MUST remain valid for 30 days and refresh on any user activity

**Configuration Management**
- **FR-007**: Users MUST be able to specify up to 5 US stock tickers per configuration (NYSE, NASDAQ, AMEX only)
- **FR-008**: Users MUST be able to specify an independent timeframe per configuration (1-365 days, limited by Finnhub 1-year free tier)
- **FR-009**: Users MUST be able to save up to 2 configurations simultaneously
- **FR-010**: System MUST allow users to switch between saved configurations within 2 seconds
- **FR-011**: System MUST allow users to edit or delete existing configurations
- **FR-012**: System MUST validate tickers using hybrid approach (local ~8K symbol cache + API validation)
- **FR-012a**: System MUST detect delisted/changed symbols, alert user, and preserve historical data

**Data & Visualization**
- **FR-013**: System MUST fetch sentiment data from BOTH Tiingo AND Finnhub for each ticker with aggressive deduplication + caching (1hr TTL) across users
- **FR-014**: System MUST display sentiment results in responsive, mobile-optimized charts
- **FR-015**: System MUST show heat map matrix visualization with user toggle between:
   - Tickers x Data Sources (Tiingo/Finnhub/Our Model)
   - Tickers x Time Periods (Today/1W/1M/3M)
- **FR-016**: System MUST show sentiment scores as numeric values (-1 to +1) with color gradient (red→yellow→green)
- **FR-017**: System MUST calculate ATR (Average True Range) using OHLC data from both Tiingo and Finnhub (redundancy)
- **FR-018**: System MUST correlate sentiment with ATR volatility using trend arrows (future: rolling correlation chart)
- **FR-019**: System MUST allow user toggle for extended hours (pre/post-market) in ATR calculation
- **FR-020**: System MUST implement circuit breaker (5 failures/5 min = open, 60s recovery)
- **FR-021**: System MUST show "last updated X ago" with countdown timer + manual refresh button (5-min refresh cycle)
- **FR-022**: If both Tiingo AND Finnhub are down, system MUST show cached data with prominent "All sources unavailable" banner

**Notifications**
- **FR-023**: Authenticated users MUST be able to set sentiment threshold alerts (e.g., "below -0.3")
- **FR-024**: Authenticated users MUST be able to set ATR volatility threshold alerts (e.g., "exceeds 3%")
- **FR-025**: System MUST send email notifications via SendGrid (API key in Secrets Manager) within 15 minutes of threshold being met
- **FR-026**: System MUST include deep link in notification email to relevant configuration view
- **FR-027**: System MUST allow users to disable notifications per ticker or globally
- **FR-028**: System MUST rate limit notifications to maximum 10 emails per user per day

**User Experience**
- **FR-029**: Dashboard MUST be mobile-first with responsive design
- **FR-030**: Dashboard MUST render beautifully on devices from 320px to 2560px width
- **FR-031**: System MUST provide visual feedback during data loading (skeleton screens, progress indicators)
- **FR-032**: System MUST handle errors gracefully with user-friendly messages

**Observability**
- **FR-033**: System MUST emit structured logs for all authentication events via AWS Lambda Powertools
- **FR-034**: System MUST track metrics for: conversion rate, Tiingo/Finnhub latency/error rate, notification delivery success rate, configuration CRUD operations
- **FR-035**: System MUST implement AWS X-Ray distributed tracing across ALL 4 Lambdas using AWSXRayDaemonWriteAccess managed policy, with SNS message attribute propagation (Day 1 mandatory - NOT Phase 2)
- **FR-036**: System MUST alert operators when Tiingo/Finnhub error rate exceeds 5% or notification delivery success drops below 95%
- **FR-037**: System MUST implement CloudWatch RUM for client-side user behavior analytics
- **FR-038**: System MUST alert operators when daily cost burn rate exceeds $3.33 (1/30th of $100 budget)

**Security & Authentication**
- **FR-039**: Sign-out MUST invalidate only current device session (not all devices)
- **FR-040**: New magic link requests MUST invalidate previous link and send notification email
- **FR-041**: Account linking (same email via magic link + OAuth) MUST require explicit user confirmation
- **FR-042**: System MUST implement IP-based rate limiting + CAPTCHA on repeated anonymous config creation
- **FR-043**: SendGrid email MUST use verified sender domain with rate limiting and spam filtering

**Infrastructure**
- **FR-044**: Static dashboard assets MUST be served via CloudFront + S3 CDN
- **FR-045**: System MUST implement volatility-aware smart allocation for API quota balancing (high-volatility tickers get priority)
- **FR-046**: During market closed hours, system MUST show predictive estimates using Finnhub pre-market quotes
- **FR-047**: Historical data (90 days for auth users) MUST be accessible via UI charts only (no API access)

**User Roles & Permissions**
- **FR-048**: System MUST support 5 MVP roles: Anonymous User, Known User, Contributor, Operator, Admin
- **FR-049**: Anonymous users MUST see heatmap preview with blurred ticker symbols (colors visible)
- **FR-050**: Role transitions (Known User → Contributor/Operator) MUST be invite-only from existing role holders
- **FR-051**: System MUST support Premium tier for Known Users (unlocks 5+ configs, 1yr history, realtime updates, CSV export)
- **FR-052**: Account deletion MUST be soft delete with 90-day recovery window

**Contributor Features**
- **FR-053**: Contributors MUST be able to create and share alert template bundles to public gallery
- **FR-054**: Template gallery MUST support browse, filter by ticker/type, and one-click import
- **FR-055**: Contributors MUST be able to directly add new tickers to symbol cache (audit logged)

**Operator Features**
- **FR-056**: Operators MUST have access to circuit breaker controls with confirm dialog safeguard
- **FR-057**: Operators MUST be able to force cache invalidation (secrets and ticker cache) without Lambda restart
- **FR-058**: Operators MUST have real-time quota dashboard with ability to pause non-critical operations
- **FR-059**: Operators MUST be able to enable system-wide alert suppression with user opt-out capability
- **FR-060**: Operators MUST be able to view and modify any user's configuration (audit logged with justification)

**Admin Features**
- **FR-061**: Admins MUST be able to impersonate any user to view dashboard as they see it (audit logged)
- **FR-062**: Admins MUST have access to alert simulator (dry-run showing what would trigger)
- **FR-063**: Admins MUST be able to trace notification delivery: evaluation → SNS → Lambda → SendGrid → status
- **FR-064**: Admins MUST be able to create feature flags with percentage rollout capability
- **FR-065**: Admins MUST have access to usage analytics (DAU, alert rates, popular tickers, error rates)
- **FR-066**: Admins MUST be able to perform bulk operations (delete inactive users, reset quotas) with audit trail
- **FR-067**: All admin and operator actions MUST be retained in audit logs for 90 days

**Advanced Known User Features**
- **FR-068**: Known Users MUST be able to compare sentiment/volatility between their 2 configs via overlay chart
- **FR-069**: Known Users MUST have access to historical replay with adaptive granularity (hourly <7d, daily >7d, weekly >30d)
- **FR-070**: Known Users MUST be able to see correlation matrix between sentiment and price movement
- **FR-071**: Known Users MUST be able to benchmark ticker sentiment against GICS sector average (11 sectors)
- **FR-072**: Known Users MUST receive notifications via both email AND browser push for all alerts

### Testing Requirements

All code changes for this feature MUST include automated tests OR provide written rationale for review. This is a mandatory quality gate.

- **TR-001**: Every new function/module MUST have unit tests covering happy path and at least one error path
- **TR-002**: Every API endpoint MUST have integration tests validating request/response contracts
- **TR-003**: Authentication flows MUST have end-to-end tests covering anonymous, magic link, and social login paths
- **TR-004**: Configuration management MUST have tests for create, read, update, delete, and validation
- **TR-005**: Notification triggers MUST have tests for threshold evaluation and email dispatch
- **TR-006**: UI components MUST have tests for responsive behavior at key breakpoints (320px, 768px, 1024px, 1440px)
- **TR-007**: If a change cannot include tests, the PR MUST include a "Test Rationale" section explaining why
- **TR-008**: Test coverage for new code MUST maintain or exceed the project's 80% threshold

### Key Entities

- **User**: Dashboard user. Anonymous (localStorage token only) or authenticated (Cognito identity). Has role (Anonymous, Known, Contributor, Operator, Admin). Owns configurations.
- **Role**: User permission level. MVP roles: Anonymous, Known User, Contributor, Operator, Admin. Future: API Consumer, Auditor, Data Steward.
- **RoleInvitation**: Pending invitation for role promotion. Created by existing role holder. Expires after 7 days.
- **Configuration**: Up to 5 tickers + timeframe. Max 2 per user (10 for Premium). Has alert rules.
- **Ticker**: US stock symbol (NYSE/NASDAQ/AMEX). Validated against ~8K symbol cache.
- **SentimentResult**: Sentiment scores from Tiingo (our model) and Finnhub (built-in). Per ticker per timestamp.
- **VolatilityMetric**: ATR calculation for a ticker. Configurable for regular vs extended hours.
- **AlertRule**: Either "sentiment_threshold" or "volatility_threshold". Has threshold value and enabled status.
- **AlertTemplate**: Reusable bundle of alert rules. Created by Contributors. Shared via public gallery.
- **Notification**: Sent alert record via SendGrid/Push. Links to rule, user, and triggering data.
- **FeatureFlag**: Admin-controlled rollout. Supports percentage-based enablement.
- **AuditLog**: Record of admin/operator actions. Includes user, action, justification, timestamp. 90-day retention.
- **CircuitBreakerState**: Per-service circuit breaker status (Tiingo, Finnhub, SendGrid). Open/Closed/Half-Open.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: New visitors can view sentiment results within 60 seconds of landing (time-to-value)
- **SC-002**: 80% of first-time visitors successfully create and view their first configuration without assistance
- **SC-003**: Dashboard loads and displays charts within 3 seconds on 3G mobile connection
- **SC-004**: 30% of anonymous users upgrade to authenticated accounts within first week
- **SC-005**: Users with notifications enabled return to dashboard 3x more frequently than those without
- **SC-006**: System supports 1,000 concurrent anonymous sessions without degradation
- **SC-007**: Email notifications delivered within 15 minutes of threshold trigger for 99% of alerts
- **SC-008**: Mobile users rate the interface 4+ stars on usability (based on in-app feedback)
- **SC-009**: Configuration switching completes in under 2 seconds for 95th percentile
- **SC-010**: Zero data loss for authenticated users across device/browser changes
- **SC-011**: Tiingo vs Finnhub sentiment displayed in heat map matrix for 100% of valid tickers
- **SC-012**: ATR correlation with sentiment shown via trend arrows for all tickers
- **SC-013**: Contributors can share alert templates that are imported by 50+ users within first month
- **SC-014**: Operators can resolve 80% of incidents without engineering escalation using self-service tools
- **SC-015**: Admin alert debugging toolkit reduces support resolution time by 50%
- **SC-016**: Feature flag rollouts complete without user-reported issues for 95% of releases
- **SC-017**: Premium tier conversion rate of 5% among active Known Users
- **SC-018**: Anonymous users who see heatmap teaser convert to Known User at 2x rate vs no preview

## Assumptions

- Tiingo free tier (500 symbols/month) sufficient with aggressive deduplication + caching
- Finnhub free tier (60 calls/minute) sufficient with 1hr cache TTL
- Browser localStorage (5MB typical) sufficient for anonymous user data
- SendGrid free tier (100 emails/day) sufficient for notification volume
- AWS Cognito supports Google and GitHub OAuth with acceptable UX
- 365-day maximum timeframe aligns with Finnhub's 1-year free tier limit
- 2 configurations per user sufficient for MVP
- Financial news data from Tiingo and Finnhub is compliant with global privacy regulations
- ~8K US stock symbols (NYSE/NASDAQ/AMEX) covers target use cases
- Hard cutover from NewsAPI acceptable (no parallel operation needed)
- Features 001-005 never deployed to production (clean slate for Feature 006)
- Daily cost burn rate alerting sufficient (vs monthly thresholds)
- CloudFront CDN acceptable latency for global users
- Lambda Powertools provides sufficient error tracking without Sentry/Rollbar

## Cost Estimates

### Normal Operation (Target: <$100/mo)
| Service | Estimate | Notes |
|---------|----------|-------|
| Tiingo API | $0 | Free tier with aggressive caching |
| Finnhub API | $0 | Free tier with 1hr cache TTL |
| SendGrid | $0 | Free tier 100 emails/day |
| Cognito | ~$5 | 50K MAU free, then $0.0055/MAU |
| Lambda | ~$10 | 4 functions, moderate traffic |
| DynamoDB | ~$15 | On-demand, 90-day retention auth users |
| CloudFront | ~$10 | ~100GB transfer/mo |
| S3 | ~$2 | Static assets + state |
| CloudWatch RUM | ~$5 | ~50K sessions/mo |
| X-Ray | ~$3 | Tracing all 4 Lambdas |
| **Total** | **~$50/mo** | 50% headroom to $100 budget |

### Attacker Cost Perspective
| Attack Vector | Mitigation | Cost to Attacker |
|---------------|------------|------------------|
| Credit exhaustion (API quotas) | IP rate limiting + CAPTCHA | Must rotate IPs ($) |
| Email bombing | 10/day/user limit + verified sender | Limited blast radius |
| Anonymous session spam | CAPTCHA + localStorage fingerprint | Automated bypass difficult |
| Magic link abuse | 1hr expiry + invalidation on re-request | Low value attack |
| Cost spike attack | Daily burn rate alerts at $3.33 | Early detection |

## Open Questions

**None remaining** - All ambiguities resolved through 16 rounds of clarification (8 original + 8 audit rounds = 60+ decisions documented above).

## Pre-Planning Actions Required

Before `/speckit.plan`, the following batch updates must complete:

1. **Create legacy/v1 branch**: Archive Features 001-005 specs
2. **Update CHANGELOG.md**: Document breaking changes from NewsAPI pivot
3. **Update CREDENTIAL-ROTATION.md**: Add Tiingo + Finnhub rotation schedules
4. **Update SECURITY_REVIEW.md**: Mark X-Ray as Day 1 mandatory
5. **Security audit findings**: Document in ../sentiment-analysis-gsk-security (private)

Ready for `/speckit.plan` phase after pre-planning actions complete.
