# Research: SPEC.md Full Documentation Audit

**Date**: 2026-01-31
**Feature**: 001-spec-doc-cleanup

## Discovery Summary

| Metric | Value |
|--------|-------|
| Total lines with Twitter-related content | **89 lines** |
| Sections affected | **10+ sections** |
| Phantom Lambdas documented | 1 (Quota Reset Lambda) |
| Actual Lambdas in codebase | 6 |

## Task 1: Twitter-Related Content Inventory

### Severity: EXTENSIVE

The SPEC.md contains **89 lines** referencing Twitter, tweets, quota_reset, or twitter_api_tier. This is not a minor cleanup - it's a fundamental documentation overhaul.

### Content Breakdown by Section

| Line Range | Section | Content Type | Action |
|------------|---------|--------------|--------|
| 16 | Architecture | "RSS/Twitter-style APIs" | MODIFY - keep generic "external APIs" |
| 40 | Dependencies | "tweepy (Twitter API v2)" | REMOVE |
| 45-70 | Twitter API Config | Entire tier-based config (Free/Basic/Pro) | REMOVE ENTIRE SECTION |
| 140, 146 | Source Config Schema | "twitter" as valid type | REMOVE "twitter" from allowlist |
| 178 | Error States | QUOTA_EXHAUSTED for Twitter | REMOVE |
| 195 | Item Schema | source_type includes "twitter" | REMOVE "twitter" option |
| 240-256 | Lambda Configuration | Twitter tier concurrency + Quota Reset Lambda | REMOVE Twitter tiers, REMOVE Quota Reset Lambda |
| 270-332 | Cost Estimates | Twitter tier pricing (~60 lines) | REMOVE OR REPLACE with Tiingo/Finnhub costs |

### Full Grep Results

```
16:- Ingestion adapters fetch from external publishing endpoints (RSS/Twitter-style APIs)
40:- Ingestion Libraries: feedparser (RSS/Atom), tweepy (Twitter API v2)
45:- Twitter API: Tier-based configuration (externalized via Terraform variable `twitter_api_tier`)
46:  - Current tier: Free ($0/month) - 1,500 tweets/month, 450 requests/15min
47:  - Upgrade path: Basic ($100/month, 50K tweets/month) → Pro ($5K/month, 1M tweets/month)
51:    - Automatic tier detection: Lambda reads TWITTER_API_TIER environment variable
56:      - 95% threshold: Emergency mode - pause all Twitter polling for 24 hours
59:      - CloudWatch metric: twitter.auto_throttle_active (boolean)
62:    - Attack Protection: max Twitter sources per tier: Free (10), Basic (50), Pro (100)
64:  - Compliance: Must follow Twitter Developer Agreement
66-70: Upgrade procedure for Twitter tiers
140:    "type": "rss",            // or "twitter"
146:- Validation rules: `type` in allowlist {"rss","twitter"}
178:    - QUOTA_EXHAUSTED: Monthly Twitter quota exceeded
195:  - source_type: "rss" or "twitter"
240-243: Ingestion concurrency tier-based (Free/Basic/Pro Twitter tiers)
245-256: Quota Reset Lambda (NOT IMPLEMENTED marker already present)
270-332: Cost Estimates heavily based on Twitter tier pricing
```

## Task 2: Lambda Inventory Comparison

### Actual Lambdas (from src/lambdas/)

| Lambda | Directory Exists | Terraform Exists | SPEC.md Documents |
|--------|------------------|------------------|-------------------|
| ingestion | ✅ | ✅ | ✅ |
| analysis | ✅ | ✅ | ✅ |
| dashboard | ✅ | ✅ | ✅ |
| metrics | ✅ | ✅ | ✅ |
| notification | ✅ | ✅ | ✅ |
| sse_streaming | ✅ | ✅ | ✅ |
| **quota_reset** | ❌ | ❌ | ⚠️ (marked NOT IMPLEMENTED) |

**Decision**: Remove Quota Reset Lambda documentation entirely (already marked as NOT IMPLEMENTED in PR #681).

## Task 3: Cross-Reference Scan

### References to Quota Reset

```
quota-reset-lambda-dlq (line 256)
Quota Reset Lambda (lines 245, 255)
monthly quota counter reset (line 245)
twitter.quota_reset_count metric (lines 251, 255)
```

### References to Twitter DLQs

```
quota-reset-lambda-dlq (line 256) - REMOVE
```

## Task 4: Other Potential Phantom Documentation

### Scan for non-Twitter phantoms

Additional patterns checked:
- `grep -i "facebook\|instagram\|tiktok" SPEC.md` → 0 matches ✅
- `grep -i "reddit\|youtube" SPEC.md` → 0 matches ✅

**Conclusion**: Twitter is the ONLY phantom data source documented. No other social media platforms are incorrectly documented.

## Recommendations

### Cleanup Strategy

1. **Remove Twitter entirely as a source type** - It was never implemented
2. **Remove Quota Reset Lambda** - Documented but never implemented
3. **Revise cost estimates** - Replace Twitter-based costs with Tiingo/Finnhub API costs
4. **Update schema examples** - Remove "twitter" from type enums
5. **Update error states** - Remove QUOTA_EXHAUSTED (Twitter-specific)

### Estimated Effort

| Task | Lines Affected | Commits |
|------|----------------|---------|
| Remove Twitter API configuration (lines 45-70) | ~25 | 1 |
| Remove Twitter from schemas (lines 140, 146, 195) | ~5 | 1 |
| Remove Quota Reset Lambda (lines 245-256) | ~12 | 1 |
| Remove/revise cost estimates (lines 270-332) | ~62 | 1-2 |
| Remove Twitter error states (line 178) | ~1 | 1 |
| Update dependencies (line 40) | ~1 | 1 |
| Final verification | N/A | 1 |

**Total**: ~100 lines affected, 6-8 atomic commits

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Remove too much | Low | Medium | Atomic commits enable rollback |
| Miss hidden references | Medium | Low | Post-cleanup grep verification |
| Break internal links | Low | Low | Markdown linter check |
| Confusion about costs | Medium | Medium | Add Tiingo/Finnhub actual costs |

## Next Steps

1. Proceed to `/speckit.tasks` to generate task list
2. Execute cleanup via atomic commits
3. Verify with grep checks after each commit
4. Final audit and PR creation
