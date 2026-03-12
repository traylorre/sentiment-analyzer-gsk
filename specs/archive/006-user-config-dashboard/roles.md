# User Roles & Use-Cases Matrix

**Feature Branch**: `006-user-config-dashboard`
**Created**: 2025-11-27
**Status**: Specification Draft

## Role Summary

| Role | Access Level | Session Type | MVP | Future |
|------|-------------|--------------|-----|--------|
| Anonymous User | Read-only preview | 30-day localStorage | Yes | - |
| Known User | Full features | 30-day authenticated | Yes | Premium tier |
| Contributor | Community features | Authenticated + invited | Yes | - |
| Operator/On-Call | System management | Authenticated + invited | Yes | - |
| Admin | Full system access | Authenticated + invited | Yes | - |
| API Consumer | Programmatic access | API key | - | Future |
| Auditor/Compliance | Read-only audit trail | Authenticated + invited | - | Future |
| Data Steward | Ticker management | Authenticated + invited | - | Future |

---

## MVP Roles (5)

### 1. Anonymous User

**Description**: First-time visitors who can experience the product without signup friction.

**Key Decisions**:
- **Preview Content**: Heatmap teaser with ticker symbols blurred, colors visible (shows sentiment patterns without specifics)
- **Session Expiry**: Cookie restore - if same browser, restore preferences from localStorage
- **Conversion Path**: "Limited preview" - must sign up to see individual tickers

**Capabilities**:
| Capability | Access |
|------------|--------|
| View market pulse (aggregated sentiment) | Yes |
| See heatmap visualization | Yes (blurred tickers) |
| Create configurations | No |
| Set alerts | No |
| Access historical data | No |
| Data persistence | Browser localStorage only |

**Use-Cases**:
1. **UC-A1**: Visitor lands on dashboard, sees blurred heatmap with sentiment colors - understands value proposition
2. **UC-A2**: Visitor sees "Sign up to see individual tickers" CTA alongside the preview
3. **UC-A3**: Visitor closes browser, returns next day on same device - preferences restored
4. **UC-A4**: Visitor's session expires after 30 days - starts fresh as new anonymous user

**Acceptance Criteria**:
- AC-A1: Anonymous user sees heatmap with colors visible but ticker symbols blurred
- AC-A2: localStorage persists view preferences for 30 days
- AC-A3: Same browser can restore preferences after restart

---

### 2. Known User (Standard)

**Description**: Authenticated users with full access to core features.

**Key Decisions**:
- **Config Limit**: 2 configurations (premium tier for 5+)
- **Config Limit Behavior**: Premium tier unlocks 5+ configs (future monetization)
- **Historical Data**: 90-day retention with adaptive granularity
- **Comparison Features**: All four enabled (cross-config, historical replay, correlation matrix, sector benchmark)
- **Notifications**: Email + browser push for all alerts

**Advanced Features**:
| Feature | Implementation |
|---------|---------------|
| Cross-config compare | Overlay chart - single chart with both configs overlaid, toggle visibility |
| Historical replay | Adaptive - hourly for <7d queries, daily for >7d, weekly for >30d |
| Correlation matrix | Both merged - Finnhub for intraday, Tiingo for historical >7d |
| Sector benchmark | GICS standard - 11 sectors |
| Data retention | 90 days of sentiment/volatility history per ticker |

**Capabilities**:
| Capability | Standard | Premium (Future) |
|------------|----------|------------------|
| Configurations | 2 | 10 |
| History depth | 90 days | 1 year |
| Update frequency | 15-min delay | Realtime |
| Export (CSV) | No | Yes |
| Custom sectors | No | Yes |
| Webhook notifications | No | Yes |
| White-label | No | Yes |

**Use-Cases**:
1. **UC-K1**: User creates "Tech Giants" config (AAPL, MSFT, GOOGL, NVDA, META)
2. **UC-K2**: User creates "EV Sector" config (TSLA, RIVN, LCID)
3. **UC-K3**: User views overlay chart comparing sentiment between both configs
4. **UC-K4**: User drills into 30-day historical replay with daily granularity
5. **UC-K5**: User sees correlation between sentiment and actual price movement
6. **UC-K6**: User compares AAPL sentiment against Information Technology sector average (GICS)
7. **UC-K7**: User sets sentiment alert for TSLA < -0.3, receives email AND browser push
8. **UC-K8**: User hits 2-config limit, sees "Upgrade to Premium" prompt

**Account Deletion**:
- Soft delete with 90-day recovery window, then permanent deletion
- User can recover account within 90 days by signing in

---

### 3. Contributor

**Description**: Engaged users who contribute to the community through templates and ticker suggestions.

**Key Decisions**:
- **Role Access**: Invite-only from existing contributors/admins
- **Alert Templates**: Public gallery - browse all shared templates, filter by ticker/type, one-click import
- **Ticker Suggestions**: Direct add - trusted contributors can add tickers directly (audit logged)

**Capabilities**:
| Capability | Access |
|------------|--------|
| All Known User features | Yes |
| Share alert templates | Yes - public gallery |
| Import community templates | Yes |
| Suggest new tickers | Yes - direct add with audit |
| Curate template gallery | No (admin only) |

**Use-Cases**:
1. **UC-C1**: Contributor creates "Earnings Season Alert Bundle" template with 5 preconfigured alerts
2. **UC-C2**: Contributor shares template to public gallery, sees import count grow
3. **UC-C3**: Contributor suggests adding "PLTR" ticker to US symbols cache, directly added
4. **UC-C4**: Other users browse gallery, filter by "tech", import Contributor's template with one click

**Acceptance Criteria**:
- AC-C1: Contributor can create and share alert templates
- AC-C2: Templates appear in public gallery with contributor attribution
- AC-C3: Ticker additions are audit logged with contributor ID
- AC-C4: Users can import templates with single click

---

### 4. Operator/On-Call

**Description**: Engineers responsible for system health and incident response.

**Key Decisions**:
- **Circuit Breaker Controls**: Confirm dialog before state change (simple, not two-person rule)
- **Cache Invalidation**: Yes - force refresh secrets cache or ticker cache without Lambda restart
- **Quota Dashboard**: Yes - real-time view of API quota usage with ability to pause non-critical ops
- **Alert Suppression**: Per user opt-in - users can opt-out of suppression for critical alerts
- **User Config Access**: Full access to modify any user config (audit logged, requires justification)

**Capabilities**:
| Capability | Access |
|------------|--------|
| All Known User features | Yes |
| Circuit breaker controls | Yes - with confirm dialog |
| Cache invalidation | Yes - secrets and ticker cache |
| Quota dashboard | Yes - real-time view |
| Alert suppression | Yes - system-wide with user opt-out |
| View user configs | Yes (audit logged) |
| Modify user configs | Yes (audit logged + justification) |
| Impersonate users | No (admin only) |

**Use-Cases**:
1. **UC-O1**: Tiingo rate limit hit - operator opens circuit breaker with confirm dialog
2. **UC-O2**: Secret rotated - operator forces cache refresh without Lambda restart
3. **UC-O3**: Quota at 80% - operator pauses non-critical background jobs
4. **UC-O4**: Scheduled maintenance - operator suppresses all alerts system-wide
5. **UC-O5**: User reports issue - operator views user's config to debug (logged)
6. **UC-O6**: User's config broken - operator fixes it directly (logged with justification)
7. **UC-O7**: Premium user opts out of suppression - their critical alerts still fire during maintenance

**Dual Failure Scenario (Tiingo + Finnhub both down)**:
- Show stale data with timestamp and "last updated X ago" badge
- Operator can monitor via quota dashboard and circuit breaker status

---

### 5. Admin

**Description**: System administrators with full access to all features and user management.

**Key Decisions**:
- **User Impersonation**: Yes - view dashboard as specific user to debug (audit logged)
- **Bulk Operations**: Yes - mass delete inactive users, reset quotas, migrate configurations
- **Feature Flags**: Percentage rollout - enable for X% of users (gradual rollout)
- **Usage Analytics**: Yes - DAU, alert trigger rates, popular tickers, error rates
- **Audit Retention**: 90 days CloudWatch (standard retention, export to S3 if needed)
- **Alert Debugging**: Complete toolkit - impersonate, simulator, and delivery trace

**Capabilities**:
| Capability | Access |
|------------|--------|
| All Operator features | Yes |
| User impersonation | Yes (audit logged) |
| Bulk operations | Yes |
| Feature flags | Yes - percentage rollout |
| Usage analytics | Yes |
| Promote users to contributor/operator | Yes |
| Alert debugging toolkit | Full (impersonate + simulator + trace) |
| Curate template gallery | Yes |

**Use-Cases**:
1. **UC-AD1**: Admin impersonates user to see exactly what they see when debugging issue
2. **UC-AD2**: Admin mass-deletes 500 inactive users (no login in 90 days)
3. **UC-AD3**: Admin enables new "heatmap v2" feature for 10% of users
4. **UC-AD4**: Admin views usage analytics - 5000 DAU, top ticker TSLA, 95% alert delivery
5. **UC-AD5**: User reports alerts never fire - admin uses full debugging toolkit:
   - Step 1: Impersonate user, view their alert config
   - Step 2: Run alert simulator dry-run showing what would trigger
   - Step 3: Trace delivery: evaluation -> SNS -> Lambda -> SendGrid -> status
6. **UC-AD6**: Admin invites power user to become Contributor role

---

## Future Roles (3)

### 6. API Consumer (Future)

**Reason Deferred**: Keep API access as future work - no external programmatic access for MVP.

**When to Add**: When we have paying customers who need integration capabilities.

---

### 7. Auditor/Compliance (Future)

**Reason Deferred**: Add when we add sentiment consumption that overlays with stock prices - that generates PII which needs careful compliance. Just consuming stock prices is not PII.

**When to Add**: When sentiment data can influence trading decisions (regulatory concern).

---

### 8. Data Steward (Future)

**Reason Deferred**: Ticker management can be handled by Admin + automated sync for MVP.

**When to Add**: When ticker cache management becomes complex enough to warrant dedicated role.

---

## Role Transitions

**Method**: Invite-only from existing role holders

| From | To | Who Can Invite |
|------|----|----------------|
| Anonymous | Known User | Self (signup) |
| Known User | Contributor | Contributor, Admin |
| Known User | Operator | Admin |
| Contributor | Operator | Admin |
| Operator | Admin | Admin |

---

## Cross-Role Scenarios

### Scenario 1: Maintenance Window
1. Admin schedules maintenance
2. Operator suppresses alerts system-wide
3. Premium Known User with critical alert opts out of suppression
4. Premium User's critical alerts still fire
5. Other users see "alerts suppressed during maintenance" message

### Scenario 2: User Escalation
1. Known User reports alerts never fire
2. Operator views user's config (logged)
3. Operator escalates to Admin
4. Admin impersonates user (logged)
5. Admin runs alert simulator - finds threshold set wrong
6. Admin contacts user with resolution

### Scenario 3: Feature Rollout
1. Admin enables "overlay comparison" for 10% of users
2. Contributor in 10% group tries it, reports bug
3. Admin disables feature (rollback)
4. Engineering fixes bug
5. Admin re-enables at 25%, then 50%, then 100%

---

## Implementation Priority

### Phase 1: MVP Roles
1. Anonymous User (basic)
2. Known User (standard)
3. Admin (minimal - user impersonation + feature flags)

### Phase 2: Community
1. Contributor (templates + ticker suggestions)
2. Operator (circuit breakers + cache + alerts)

### Phase 3: Advanced Admin
1. Admin bulk operations
2. Admin usage analytics
3. Full alert debugging toolkit

### Phase 4: Future Roles
1. API Consumer
2. Auditor/Compliance
3. Data Steward
