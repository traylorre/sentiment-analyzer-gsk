# Implementation Plan: Sentiment Dashboard Frontend

**Branch**: `007-sentiment-dashboard-frontend` | **Date**: 2025-11-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-sentiment-dashboard-frontend/spec.md`

## Summary

Build a mobile-first, gesture-based frontend dashboard for the Financial News Sentiment Analyzer using Next.js 14+ App Router with shadcn/ui components and TradingView Lightweight Charts. The frontend consumes Feature 006's backend APIs and deploys via AWS Amplify. Focus is on polish-first: 60fps animations, <200ms interactions, Robinhood-style dark fintech aesthetic with cyan accents.

## Technical Context

**Language/Version**: TypeScript 5.x, Node.js 20 LTS
**Framework**: Next.js 14+ (App Router with Server Components)
**UI Library**: shadcn/ui (Tailwind CSS + Radix UI primitives)
**Charting**: TradingView Lightweight Charts (~40kb, financial-optimized)
**Animation**: Framer Motion (gesture physics, spring animations)
**State Management**: Zustand (lightweight) + React Query (server state)
**Testing**: Vitest (unit), Playwright (E2E), React Testing Library
**Target Platform**: Web (mobile-first responsive, 320px-2560px)
**Deployment**: AWS Amplify (Next.js SSR support, auto-scaling)
**Performance Goals**: 60fps animations, <200ms interaction feedback, <3s initial load on 3G
**Constraints**: No PWA, no keyboard shortcuts, dark theme only
**Scale/Scope**: ~15 pages/views, ~50 components, 1000+ concurrent users

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| TLS required | ✅ PASS | AWS Amplify enforces HTTPS by default |
| Auth required for admin | ✅ PASS | No admin endpoints in frontend; user auth via Cognito |
| Secrets in managed service | ✅ PASS | API keys stored in Amplify environment variables |
| No raw text logging | ✅ PASS | Frontend logs events, not content |
| Health checks | ✅ PASS | Next.js built-in health endpoint |
| IaC deployment | ✅ PASS | Amplify configured via amplify.yml |
| Unit test coverage 80%+ | ✅ PASS | Vitest for components, hooks, utilities |
| GPG-signed commits | ✅ PASS | Git workflow enforced |
| No pipeline bypass | ✅ PASS | Amplify CI/CD with required checks |

**No violations requiring justification.**

## Project Structure

### Documentation (this feature)

```text
specs/007-sentiment-dashboard-frontend/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (frontend state models)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API client contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── (auth)/             # Auth route group
│   │   │   ├── login/
│   │   │   └── callback/
│   │   ├── (dashboard)/        # Dashboard route group
│   │   │   ├── page.tsx        # Main dashboard
│   │   │   ├── configs/        # Configuration management
│   │   │   ├── alerts/         # Alert management
│   │   │   └── settings/       # User settings
│   │   ├── layout.tsx          # Root layout
│   │   ├── globals.css         # Tailwind + custom styles
│   │   └── providers.tsx       # Context providers
│   │
│   ├── components/
│   │   ├── ui/                 # shadcn/ui components
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── input.tsx
│   │   │   ├── sheet.tsx       # Bottom sheet
│   │   │   ├── skeleton.tsx
│   │   │   ├── slider.tsx
│   │   │   ├── switch.tsx
│   │   │   ├── toast.tsx
│   │   │   └── tooltip.tsx
│   │   │
│   │   ├── charts/             # TradingView Lightweight Charts wrappers
│   │   │   ├── sentiment-chart.tsx
│   │   │   ├── sparkline.tsx
│   │   │   ├── heat-map.tsx
│   │   │   └── chart-crosshair.tsx
│   │   │
│   │   ├── gestures/           # Gesture components
│   │   │   ├── swipe-view.tsx
│   │   │   ├── pull-to-refresh.tsx
│   │   │   └── bottom-sheet.tsx
│   │   │
│   │   ├── auth/               # Authentication components
│   │   │   ├── auth-modal.tsx
│   │   │   ├── magic-link-form.tsx
│   │   │   ├── oauth-buttons.tsx
│   │   │   └── success-animation.tsx
│   │   │
│   │   ├── dashboard/          # Dashboard-specific components
│   │   │   ├── ticker-input.tsx
│   │   │   ├── config-card.tsx
│   │   │   ├── alert-card.tsx
│   │   │   ├── refresh-countdown.tsx
│   │   │   └── connection-status.tsx
│   │   │
│   │   └── layout/             # Layout components
│   │       ├── mobile-nav.tsx
│   │       ├── desktop-nav.tsx
│   │       ├── header.tsx
│   │       └── page-transition.tsx
│   │
│   ├── hooks/                  # Custom React hooks
│   │   ├── use-gesture.ts
│   │   ├── use-haptic.ts
│   │   ├── use-animation.ts
│   │   ├── use-sse.ts
│   │   ├── use-auth.ts
│   │   ├── use-configs.ts
│   │   └── use-reduced-motion.ts
│   │
│   ├── lib/                    # Utilities and clients
│   │   ├── api/                # API client (generated from contracts)
│   │   │   ├── client.ts
│   │   │   ├── auth.ts
│   │   │   ├── configs.ts
│   │   │   ├── sentiment.ts
│   │   │   └── alerts.ts
│   │   ├── utils/
│   │   │   ├── cn.ts           # Class name utility
│   │   │   ├── haptics.ts      # Haptic feedback
│   │   │   ├── colors.ts       # Sentiment color mapping
│   │   │   └── format.ts       # Number/date formatting
│   │   └── constants.ts
│   │
│   ├── stores/                 # Zustand stores
│   │   ├── auth-store.ts
│   │   ├── view-store.ts
│   │   ├── config-store.ts
│   │   └── animation-store.ts
│   │
│   └── types/                  # TypeScript types
│       ├── api.ts
│       ├── sentiment.ts
│       ├── config.ts
│       └── auth.ts
│
├── tests/
│   ├── unit/                   # Vitest unit tests
│   │   ├── components/
│   │   ├── hooks/
│   │   └── lib/
│   └── e2e/                    # Playwright E2E tests
│       ├── auth.spec.ts
│       ├── dashboard.spec.ts
│       └── gestures.spec.ts
│
├── public/
│   └── fonts/                  # Inter font (Robinhood-style)
│
├── amplify.yml                 # AWS Amplify build config
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
├── vitest.config.ts
├── playwright.config.ts
└── package.json
```

**Structure Decision**: Frontend-only project using Next.js App Router. Backend is Feature 006 (separate deployment). This follows the "Web application" pattern with frontend as a standalone deployable unit consuming external APIs.

## Complexity Tracking

> No violations requiring justification.
