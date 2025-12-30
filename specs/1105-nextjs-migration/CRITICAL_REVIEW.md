# CRITICAL REVIEW: Spec 1105 - Next.js Migration

**Reviewer**: Principal Engineer Analysis
**Date**: 2025-12-29
**Status**: SPEC HAS FATAL FLAW - REQUIRES REVISION

---

## Executive Summary

Spec 1105 proposes migrating from vanilla JS to Next.js using `output: 'export'` (static export) to S3. **This approach is impossible** due to Next.js runtime dependencies.

**Recommendation**: Revise spec to use AWS Amplify SSR or Vercel deployment.

---

## Fatal Flaw: Static Export Incompatibility

### The Assumption

Spec 1105 Phase 1 states:
```javascript
// next.config.js
const nextConfig = {
  output: 'export',  // Enable static HTML export
  trailingSlash: true,
  images: { unoptimized: true },
};
```

### The Reality

The Next.js frontend has **8 critical blockers** that prevent static export:

| Blocker | Location | Reason |
|---------|----------|--------|
| Middleware | `middleware.ts` | Runtime auth redirects |
| useSearchParams | `auth/verify/page.tsx` | URL parameter parsing |
| useRouter | Multiple files | Programmatic navigation |
| SessionProvider | `session-provider.tsx` | Runtime auth state |
| RuntimeInitializer | `providers.tsx` | API fetch at startup |
| 'use client' | All 8 pages | Browser runtime required |
| Zustand stores | Auth, config | State persistence |
| Browser APIs | Throughout | localStorage, cookies |

### Canonical Source

From [Next.js Static Export Documentation](https://nextjs.org/docs/app/building-your-application/deploying/static-exports):

> **Unsupported Features with Static Export:**
> - Middleware
> - Rewrites and Redirects in next.config.js
> - Headers in next.config.js
> - Incremental Static Regeneration
> - Image Optimization (with default loader)
> - Draft Mode

**The frontend is a Single Page Application with authentication—not a static site.**

---

## Conflicting Specs (12 Identified)

| Spec ID | Title | Impact |
|---------|-------|--------|
| 1057 | OHLC Chart Vanilla JS | Superseded |
| 1035 | Resolution Selector | Superseded |
| 1084 | Hide Hybrid Resolutions | Superseded |
| 1050 | Metrics Session Race | Not needed |
| 1011 | Dashboard Auth Header | Architecture mismatch |
| 1018 | Resolution Switch Perf | Re-instrument needed |
| 1019 | SSE Latency Testing | Re-validate needed |
| 1021a | Skeleton Loading UI | Already in Next.js |
| 1021b | Resolution Config | Already in Next.js |
| 113 | Dashboard S3 Deploy | Superseded |
| 1036 | Container Deploy | Reorder required |
| 104 | Interview URL | Compatible |

---

## Blind Spots

### 1. SSE URL Discovery Circular Dependency

Next.js fetches SSE URL from `/api/v2/runtime` on Lambda. If Lambda stops serving frontend, this endpoint must remain accessible via CloudFront → API Gateway path.

### 2. Magic Link Verification

`useSearchParams()` parses `?token=abc123` from magic link URLs. Static export cannot read URL parameters—this flow breaks entirely.

### 3. CORS and Cookie Authentication

Moving frontend to new domain (S3/CloudFront) may break:
- CORS preflight (new origin not allowed)
- Cookie delivery (`SameSite` restrictions)
- Credential handling (`credentials: 'include'`)

### 4. CloudFront SPA Routing

Current error page config (`404 → /index.html`) assumes client-side routing. Next.js middleware operates server-side, breaking this pattern.

---

## Viable Alternatives

### Option A: Vercel (Recommended for Speed)

**Canonical source**: https://vercel.com/docs/frameworks/nextjs

- Zero config for Next.js
- Middleware works natively
- Built by Next.js team
- Free tier available

**Trade-off**: Third-party, data leaves AWS

### Option B: AWS Amplify SSR (Recommended for AWS)

**Canonical source**: https://docs.aws.amazon.com/amplify/latest/userguide/server-side-rendering-amplify.html

- Stays in AWS ecosystem
- Supports Next.js SSR + middleware
- Integrates with existing infrastructure

**Trade-off**: More complex setup

### Option C: Lambda@Edge (Complex)

**Canonical source**: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/lambda-at-the-edge.html

- S3 for static assets
- Lambda@Edge reimplements middleware
- Edge execution for low latency

**Trade-off**: Manual middleware reimplementation, Lambda@Edge limits

### Option D: Fix Chart.js Only (Pragmatic)

Keep current architecture, replace Chart.js with lightweight-charts in vanilla JS.

- Minimal change
- No deployment changes
- Fastest to implement

**Trade-off**: Technical debt remains, two frontends

---

## Failure Modes

| Scenario | Likelihood | Impact | Detection |
|----------|------------|--------|-----------|
| Build fails with static export | 100% | Blocks deployment | Immediate CI failure |
| Auth redirects stop working | High (if middleware removed) | Users see broken UI | User reports |
| CORS failures on new domain | Medium | API calls fail | Browser console |
| SSE connection fails | Medium | No real-time updates | Silent failure |
| Cookies not sent | Medium | Auth loops | User reports |

---

## Recommended Path Forward

### If Demo Timeline is Tight

**Option D**: Fix Chart.js in vanilla JS
- Replace Chart.js with lightweight-charts (port from Next.js)
- Add gap visualization
- Keep current deployment

### If Long-Term Architecture Matters

**Option B**: AWS Amplify SSR
- Deploy Next.js to Amplify
- Configure custom domain
- Update CloudFront to point to Amplify
- Deprecate Lambda static serving
- Delete `/src/dashboard/`

---

## Action Items

1. [ ] **Revise spec 1105** to reflect viable deployment strategy
2. [ ] **Stakeholder decision** on deployment target (Vercel vs Amplify vs Chart.js fix)
3. [ ] **Update conflicting specs** (mark as superseded or reorder)
4. [ ] **Test CORS/cookie behavior** if changing frontend domain
5. [ ] **Validate SSE URL discovery** works via CloudFront → API Gateway

---

## References

- Next.js Static Export: https://nextjs.org/docs/app/building-your-application/deploying/static-exports
- Vercel Deployment: https://vercel.com/docs/frameworks/nextjs
- AWS Amplify SSR: https://docs.aws.amazon.com/amplify/latest/userguide/server-side-rendering-amplify.html
- Lambda@Edge: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/lambda-at-the-edge.html
- Next.js Middleware: https://nextjs.org/docs/app/building-your-application/routing/middleware
