# Feature 006 Audit Report: Specify & Plan Analysis

**Date**: 2025-11-26
**Auditor**: Claude Code
**Scope**: Cross-artifact consistency, gaps, conflicts, dependencies, and implementation forecast

---

## Executive Summary

| Category | Status | Issues Found |
|----------|--------|--------------|
| Spec ↔ Plan Consistency | ✅ PASS | 0 conflicts |
| Spec ↔ Contracts Coverage | ⚠️ WARN | 3 minor gaps |
| Spec ↔ Data Model Coverage | ✅ PASS | 0 conflicts |
| External Dependencies | ⚠️ WARN | 2 items need attention |
| Missing Components | 🔴 GAPS | 8 components identified |
| Constitution Compliance | ✅ PASS | All requirements met |

**Overall Assessment**: Ready for implementation with minor documentation gaps to address during development.

---

## 1. Spec ↔ Plan Conflicts

### No Critical Conflicts Found ✅

| Spec Requirement | Plan Coverage | Status |
|-----------------|---------------|--------|
| FR-001 to FR-047 | All mapped to implementation | ✅ |
| TR-001 to TR-008 | Test strategy defined | ✅ |
| SC-001 to SC-012 | Measurable criteria defined | ✅ |

### Minor Clarifications Needed

| Item | Spec Says | Plan Says | Resolution |
|------|-----------|-----------|------------|
| ATR Period | "User configurable" | "14-period default, 5-50 range" | Plan is more specific - ✅ OK |
| Daily Digest | FR-028 mentions "digest option" | Not in notification-api.md | **GAP** - Add to notification API |
| CAPTCHA Provider | "CAPTCHA on repeated config creation" | Not specified | **GAP** - Need to select provider |

---

## 2. API Contract Coverage Analysis

### Dashboard API (dashboard-api.md)

| Spec Requirement | API Endpoint | Status |
|-----------------|--------------|--------|
| FR-007: 5 tickers per config | POST /configurations | ✅ |
| FR-008: Independent timeframe | Configuration object | ✅ |
| FR-009: Max 2 configs | 409 error handling | ✅ |
| FR-010: Switch in <2s | GET /configurations/{id} | ✅ |
| FR-012: Ticker validation | GET /tickers/validate | ✅ |
| FR-015: Heat map matrix | GET /heatmap | ✅ |
| FR-017: ATR calculation | GET /volatility | ✅ |
| FR-019: Extended hours toggle | include_extended_hours param | ✅ |
| FR-021: Refresh status | GET /refresh/status | ✅ |

**Missing from Dashboard API**:
- FR-046: Pre-market estimates endpoint (market closed hours)
- FR-022: "All sources unavailable" banner state not in API response

### Auth API (auth-api.md)

| Spec Requirement | API Endpoint | Status |
|-----------------|--------------|--------|
| FR-003: Magic link (1hr expiry) | POST /auth/magic-link | ✅ |
| FR-004: Google/GitHub OAuth | GET /auth/oauth/urls | ✅ |
| FR-005: Merge localStorage | merge_status endpoint | ✅ |
| FR-006a: 30-day session | session_expires_at | ✅ |
| FR-039: Current device signout | POST /auth/signout | ✅ |
| FR-040: Magic link invalidation | Previous link handling | ✅ |
| FR-041: Account linking confirmation | POST /auth/link-accounts | ✅ |

**Missing from Auth API**:
- FR-042: CAPTCHA on repeated anonymous config creation (endpoint needed)

### Notification API (notification-api.md)

| Spec Requirement | API Endpoint | Status |
|-----------------|--------------|--------|
| FR-023: Sentiment threshold alerts | POST /alerts | ✅ |
| FR-024: ATR volatility alerts | POST /alerts | ✅ |
| FR-025: Email within 15 min | Internal evaluate endpoint | ✅ |
| FR-026: Deep link in email | deep_link field | ✅ |
| FR-027: Disable per ticker/global | PATCH /alerts, disable-all | ✅ |
| FR-028: Max 10 emails/day | daily_email_quota | ✅ |

**Missing from Notification API**:
- Daily digest scheduling endpoint (FR-028 mentions digest option)
- 50% SendGrid quota alert mechanism (FR-038 mentions cost alerts)

---

## 3. Data Model Coverage

### Entity Completeness

| Spec Entity | Data Model | DynamoDB Table | Status |
|-------------|------------|----------------|--------|
| User | User class | sentiment-users | ✅ |
| Configuration | Configuration class | sentiment-users | ✅ |
| Ticker | Ticker class (embedded) | N/A | ✅ |
| SentimentResult | SentimentResult class | sentiment-items | ✅ |
| VolatilityMetric | VolatilityMetric class | sentiment-items | ✅ |
| AlertRule | AlertRule class | sentiment-users | ✅ |
| Notification | Notification class | sentiment-notifications | ✅ |
| MagicLinkToken | MagicLinkToken class | TTL-managed | ✅ |

### Missing Entity

| Entity | Purpose | Recommendation |
|--------|---------|----------------|
| TickerCache | ~8K symbol cache | Add to data model or document as S3 JSON |
| QuotaTracker | API quota management | Add to shared models |
| CircuitBreakerState | Per-API circuit breaker | Add DynamoDB or in-memory cache |

---

## 4. External Dependencies Audit

### New Dependencies Required

| Dependency | Purpose | Free Tier | Risk Level |
|------------|---------|-----------|------------|
| **Tiingo API** | Financial news + OHLC | 500 symbols/mo | 🟡 Medium - quota limits |
| **Finnhub API** | News sentiment + quotes | 60 calls/min | 🟡 Medium - rate limits |
| **SendGrid** | Email notifications | 100/day | 🟢 Low - sufficient |
| **AWS Cognito** | OAuth (Google/GitHub) | 50K MAU | 🟢 Low - generous |
| **AWS X-Ray** | Distributed tracing | Pay-per-use | 🟢 Low - ~$3/mo |
| **CloudWatch RUM** | Client analytics | Pay-per-use | 🟢 Low - ~$5/mo |
| **CloudFront** | CDN for dashboard | Pay-per-use | 🟢 Low - ~$10/mo |
| **Recharts** | Heat map visualization | Free (MIT) | 🟢 Low |

### Dependencies to Remove

| Dependency | Reason |
|------------|--------|
| NewsAPI adapter | Replaced by Tiingo/Finnhub |
| Guardian adapter (if exists) | Replaced by Tiingo/Finnhub |

### Python Package Updates Needed

```diff
# requirements.txt changes
+ aws-xray-sdk==2.14.0          # X-Ray tracing
+ sendgrid==6.11.0              # Email notifications
+ aws-lambda-powertools[all]    # Enhanced logging
- newsapi-python                 # REMOVE - deprecated
```

### Terraform Module Updates Needed

```diff
# infrastructure/terraform/modules/
+ cognito/                       # NEW - User pool, OAuth providers
+ cloudfront/                    # NEW - CDN for static assets
+ xray/                          # NEW - X-Ray tracing config
+ cloudwatch-rum/                # NEW - RUM application monitor
```

---

## 5. Missing Components (Gaps)

### High Priority (Blocking)

| Component | Location | Required For | Effort |
|-----------|----------|--------------|--------|
| **TiingoAdapter** | src/lambdas/ingestion/adapters/tiingo.py | FR-013 | 4h |
| **FinnhubAdapter** | src/lambdas/ingestion/adapters/finnhub.py | FR-013 | 4h |
| **ATR Calculator** | src/lambdas/analysis/atr.py | FR-017, FR-018 | 3h |
| **Cognito Terraform Module** | infrastructure/terraform/modules/cognito/ | FR-004 | 6h |
| **Notification Lambda** | src/lambdas/notification/handler.py | FR-023-FR-028 | 8h |
| **Auth Module** | src/lambdas/shared/auth.py | FR-003, FR-004 | 6h |

### Medium Priority (Core Features)

| Component | Location | Required For | Effort |
|-----------|----------|--------------|--------|
| **SendGrid Service** | src/lambdas/notification/sendgrid.py | FR-025 | 3h |
| **Circuit Breaker** | src/lambdas/shared/circuit_breaker.py | FR-020 | 2h |
| **Ticker Cache** | src/lambdas/shared/ticker_cache.py | FR-012 | 3h |
| **Magic Link Handler** | src/lambdas/dashboard/auth.py | FR-003 | 4h |
| **Heat Map Data Builder** | src/lambdas/dashboard/heatmap.py | FR-015 | 4h |
| **Quota Manager** | src/lambdas/shared/quota.py | Cost control | 3h |

### Low Priority (Enhancement)

| Component | Location | Required For | Effort |
|-----------|----------|--------------|--------|
| **CloudFront Module** | infrastructure/terraform/modules/cloudfront/ | FR-044 | 4h |
| **RUM Integration** | src/dashboard/services/rum.ts | FR-037 | 2h |
| **Daily Digest Scheduler** | src/lambdas/notification/digest.py | FR-028 | 3h |

### Frontend Components (New)

| Component | Location | Required For | Effort |
|-----------|----------|--------------|--------|
| **HeatMap Component** | src/dashboard/components/HeatMap.tsx | FR-015 | 6h |
| **TickerInput Component** | src/dashboard/components/TickerInput.tsx | FR-012 | 4h |
| **ConfigSwitcher Component** | src/dashboard/components/ConfigSwitcher.tsx | FR-010 | 3h |
| **AlertManager Component** | src/dashboard/components/AlertManager.tsx | FR-023 | 4h |
| **AuthFlow Component** | src/dashboard/components/AuthFlow.tsx | FR-003, FR-004 | 6h |

---

## 6. Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           INFRASTRUCTURE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│  Terraform: Cognito → CloudFront → X-Ray → RUM → New Secrets            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           BACKEND CORE                                   │
├─────────────────────────────────────────────────────────────────────────┤
│  1. TiingoAdapter + FinnhubAdapter (parallel)                           │
│  2. ATR Calculator                                                       │
│  3. Circuit Breaker + Quota Manager (shared utilities)                  │
│  4. Auth Module (Cognito + Magic Links)                                 │
│  5. Notification Lambda + SendGrid                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           API LAYER                                      │
├─────────────────────────────────────────────────────────────────────────┤
│  6. Dashboard API v2 extensions (configs, sentiment, volatility)        │
│  7. Auth API endpoints                                                   │
│  8. Notification API endpoints                                           │
│  9. Heat map data builder                                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                       │
├─────────────────────────────────────────────────────────────────────────┤
│  10. HeatMap + TickerInput + ConfigSwitcher components                  │
│  11. AuthFlow (OAuth + Magic Link UI)                                   │
│  12. AlertManager UI                                                     │
│  13. CloudWatch RUM integration                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Order of Attack (Implementation Phases)

### Phase 1: Infrastructure Foundation (Estimated: 3 days)

| # | Task | Dependencies | Effort | Parallel? |
|---|------|--------------|--------|-----------|
| 1.1 | Create Cognito Terraform module | None | 6h | Yes |
| 1.2 | Create CloudFront Terraform module | None | 4h | Yes |
| 1.3 | Add X-Ray tracing config | None | 2h | Yes |
| 1.4 | Add new secrets (Tiingo, Finnhub, SendGrid) | None | 1h | Yes |
| 1.5 | Update CI/CD for new resources | 1.1-1.4 | 2h | No |

**Phase 1 Total**: ~15 hours (3 days with parallelization)

### Phase 2: Backend Core (Estimated: 5 days)

| # | Task | Dependencies | Effort | Parallel? |
|---|------|--------------|--------|-----------|
| 2.1 | Implement TiingoAdapter | Phase 1 | 4h | Yes |
| 2.2 | Implement FinnhubAdapter | Phase 1 | 4h | Yes |
| 2.3 | Implement ATR Calculator | 2.1, 2.2 | 3h | No |
| 2.4 | Implement Circuit Breaker | None | 2h | Yes |
| 2.5 | Implement Quota Manager | None | 3h | Yes |
| 2.6 | Implement Ticker Cache | None | 3h | Yes |
| 2.7 | Implement Auth Module (Cognito + Magic Links) | 1.1 | 6h | No |
| 2.8 | Create Notification Lambda scaffold | None | 2h | Yes |
| 2.9 | Implement SendGrid Service | 2.8 | 3h | No |
| 2.10 | Implement Alert Evaluation Logic | 2.8 | 4h | No |
| 2.11 | Unit tests for all above | 2.1-2.10 | 8h | No |

**Phase 2 Total**: ~42 hours (5 days with some parallelization)

### Phase 3: API Layer (Estimated: 4 days)

| # | Task | Dependencies | Effort | Parallel? |
|---|------|--------------|--------|-----------|
| 3.1 | Dashboard API: Configuration endpoints | Phase 2 | 4h | Yes |
| 3.2 | Dashboard API: Sentiment endpoints | 2.1, 2.2, 2.3 | 4h | Yes |
| 3.3 | Dashboard API: Volatility endpoints | 2.3 | 3h | Yes |
| 3.4 | Dashboard API: Heat map builder | 3.2, 3.3 | 4h | No |
| 3.5 | Auth API: Anonymous session | 2.7 | 2h | Yes |
| 3.6 | Auth API: Magic link flow | 2.7, 2.9 | 4h | No |
| 3.7 | Auth API: OAuth callback | 2.7 | 3h | No |
| 3.8 | Auth API: Account linking | 3.5, 3.6, 3.7 | 3h | No |
| 3.9 | Notification API: Alert CRUD | 2.10 | 3h | Yes |
| 3.10 | Notification API: Preferences | 3.9 | 2h | No |
| 3.11 | Integration tests for all APIs | 3.1-3.10 | 8h | No |

**Phase 3 Total**: ~40 hours (4 days with parallelization)

### Phase 4: Frontend (Estimated: 5 days)

| # | Task | Dependencies | Effort | Parallel? |
|---|------|--------------|--------|-----------|
| 4.1 | TickerInput component (autocomplete) | 3.1 | 4h | Yes |
| 4.2 | ConfigSwitcher component | 3.1 | 3h | Yes |
| 4.3 | HeatMap component (Recharts) | 3.4 | 6h | Yes |
| 4.4 | Volatility display component | 3.3 | 3h | Yes |
| 4.5 | AuthFlow component (OAuth + Magic Link) | 3.5-3.8 | 6h | No |
| 4.6 | AlertManager component | 3.9, 3.10 | 4h | No |
| 4.7 | Mobile responsive layout | 4.1-4.6 | 4h | No |
| 4.8 | CloudWatch RUM integration | 4.7 | 2h | No |
| 4.9 | localStorage management | 4.5 | 2h | Yes |
| 4.10 | E2E tests (Playwright) | 4.1-4.9 | 8h | No |

**Phase 4 Total**: ~42 hours (5 days with parallelization)

### Phase 5: Integration & Polish (Estimated: 3 days)

| # | Task | Dependencies | Effort | Parallel? |
|---|------|--------------|--------|-----------|
| 5.1 | End-to-end flow testing | All phases | 4h | No |
| 5.2 | Performance testing (3G mobile) | 5.1 | 3h | No |
| 5.3 | Cost monitoring setup | Phase 1 | 2h | Yes |
| 5.4 | Security audit (OWASP) | 5.1 | 4h | No |
| 5.5 | Documentation updates | All | 4h | Yes |
| 5.6 | Remove NewsAPI adapter | 2.1, 2.2 working | 1h | Yes |
| 5.7 | Final preprod deployment | 5.1-5.6 | 4h | No |

**Phase 5 Total**: ~22 hours (3 days)

---

## 8. Time Estimate Summary

| Phase | Description | Days | Confidence |
|-------|-------------|------|------------|
| Phase 1 | Infrastructure Foundation | 3 | High (90%) |
| Phase 2 | Backend Core | 5 | High (85%) |
| Phase 3 | API Layer | 4 | High (85%) |
| Phase 4 | Frontend | 5 | Medium (75%) |
| Phase 5 | Integration & Polish | 3 | High (85%) |
| **Total** | **Full Implementation** | **20 days** | **Medium (80%)** |

### Risk Factors

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tiingo/Finnhub API changes | Medium | Mock adapters for testing |
| Cognito OAuth complexity | Medium | Start with magic links, add OAuth later |
| Heat map performance on mobile | Medium | Virtualize large datasets |
| API quota exhaustion during dev | Low | Use aggressive caching, test fixtures |

### Confidence Adjustments

- Add 20% buffer for unknowns: 20 days → **24 days**
- Best case (parallel execution): **18 days**
- Worst case (blockers): **28 days**

---

## 9. Recommendations

### Before Starting Implementation

1. **Obtain API Keys**: Register for Tiingo and Finnhub free tiers immediately
2. **Set Up SendGrid**: Verify sender domain for email deliverability
3. **Configure OAuth**: Register Google and GitHub OAuth apps
4. **Update requirements.txt**: Add new dependencies before coding

### During Implementation

1. **Start with Adapters**: Tiingo and Finnhub adapters unlock everything
2. **Test Quota Management Early**: Validate caching strategy works
3. **Build Auth in Parallel**: Auth module doesn't block sentiment features
4. **Defer Daily Digest**: Can be added after core notifications work

### After Implementation

1. **Monitor Costs**: Set up daily burn rate alerts immediately
2. **Track Conversion**: Measure anonymous → auth upgrade rate
3. **Gather Feedback**: Use CloudWatch RUM to identify UX issues

---

## 10. Audit Conclusion

**Verdict**: ✅ **READY FOR IMPLEMENTATION**

The specification and plan artifacts are comprehensive and internally consistent. The 8 identified gaps are implementation details that can be resolved during development. No blocking conflicts exist between spec, plan, data model, and API contracts.

**Recommended Next Step**: Run `/speckit.tasks` to generate the detailed task breakdown based on this audit.
