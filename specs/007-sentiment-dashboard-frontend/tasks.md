# Tasks: Sentiment Dashboard Frontend

**Input**: Design documents from `/specs/007-sentiment-dashboard-frontend/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included per constitution requirements (80%+ coverage)

**Organization**: Tasks grouped by user story for independent implementation

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story this task belongs to (US1-US8)
- All paths relative to `frontend/` directory

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Initialize Next.js project with all dependencies and configuration

- [ ] T001 Create frontend directory and initialize Next.js 14 project with App Router in frontend/
- [ ] T002 Install core dependencies (lightweight-charts, framer-motion, zustand, @tanstack/react-query) in frontend/package.json
- [ ] T003 [P] Initialize shadcn/ui and add required components (button, card, dialog, input, sheet, skeleton, slider, switch, toast, tooltip) in frontend/src/components/ui/
- [ ] T004 [P] Configure Tailwind with dark fintech theme (cyan accents, glassmorphism) in frontend/tailwind.config.ts
- [ ] T005 [P] Create global CSS with dark theme variables and animations in frontend/src/app/globals.css
- [ ] T006 [P] Configure Vitest for unit testing in frontend/vitest.config.ts
- [ ] T007 [P] Configure Playwright for E2E testing in frontend/playwright.config.ts
- [ ] T008 [P] Create test setup file with mocks for haptics and matchMedia in frontend/tests/setup.ts
- [ ] T009 [P] Create AWS Amplify configuration in frontend/amplify.yml
- [ ] T010 [P] Configure environment variables template in frontend/.env.example

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure required by ALL user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### TypeScript Types (All Stories Depend On)

- [ ] T011 [P] Create sentiment types (SentimentScore, TickerSentiment, SentimentData) in frontend/src/types/sentiment.ts
- [ ] T012 [P] Create config types (Configuration, CreateConfigRequest, UpdateConfigRequest) in frontend/src/types/config.ts
- [ ] T013 [P] Create auth types (User, AuthTokens, AuthState) in frontend/src/types/auth.ts
- [ ] T014 [P] Create alert types (AlertRule, AlertList, CreateAlertRequest) in frontend/src/types/alert.ts
- [ ] T015 [P] Create connection types (ConnectionStatus, RefreshState) in frontend/src/types/connection.ts
- [ ] T016 [P] Create heat map types (HeatMapCell, HeatMapRow, HeatMapData) in frontend/src/types/heatmap.ts

### API Client (All Stories Depend On)

- [ ] T017 Create base API client with error handling in frontend/src/lib/api/client.ts
- [ ] T018 [P] Create auth API client in frontend/src/lib/api/auth.ts
- [ ] T019 [P] Create configs API client in frontend/src/lib/api/configs.ts
- [ ] T020 [P] Create sentiment API client in frontend/src/lib/api/sentiment.ts
- [ ] T021 [P] Create alerts API client in frontend/src/lib/api/alerts.ts
- [ ] T022 [P] Create tickers API client (search/validate) in frontend/src/lib/api/tickers.ts
- [ ] T023 Create API index file exporting all clients in frontend/src/lib/api/index.ts

### Utility Functions (All Stories Depend On)

- [ ] T024 [P] Create cn() utility for class names in frontend/src/lib/utils/cn.ts
- [ ] T025 [P] Create haptics utility with light/medium/heavy feedback in frontend/src/lib/utils/haptics.ts
- [ ] T026 [P] Create sentiment color mapping utility in frontend/src/lib/utils/colors.ts
- [ ] T027 [P] Create number/date formatting utilities in frontend/src/lib/utils/format.ts
- [ ] T028 [P] Create constants file (API URL, refresh intervals) in frontend/src/lib/constants.ts

### Core Hooks (All Stories Depend On)

- [ ] T029 [P] Create useReducedMotion hook for accessibility in frontend/src/hooks/use-reduced-motion.ts
- [ ] T030 [P] Create useHaptic hook with reduced motion support in frontend/src/hooks/use-haptic.ts

### App Shell (All Stories Depend On)

- [ ] T031 Create root layout with providers wrapper in frontend/src/app/layout.tsx
- [ ] T032 Create providers component (QueryClient, Zustand hydration) in frontend/src/app/providers.tsx
- [ ] T033 [P] Create loading skeleton component in frontend/src/components/ui/loading-skeleton.tsx

### Unit Tests for Foundational

- [ ] T034 [P] Unit test for API client error handling in frontend/tests/unit/lib/api/client.test.ts
- [ ] T035 [P] Unit test for color utility functions in frontend/tests/unit/lib/utils/colors.test.ts
- [ ] T036 [P] Unit test for haptics utility in frontend/tests/unit/lib/utils/haptics.test.ts

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - First Impression & Instant Value (Priority: P1) 🎯 MVP

**Goal**: Beautiful dark dashboard with ticker input, autocomplete, and animated sentiment chart that wows first-time visitors

**Independent Test**: Load dashboard on mobile, enter "AAPL", verify chart renders with 60fps animations within 3 seconds, haptic feedback on tap

### Zustand Stores for US1

- [ ] T037 [P] [US1] Create animation store with queue and preferences in frontend/src/stores/animation-store.ts
- [ ] T038 [P] [US1] Create chart store with ticker/scrub state in frontend/src/stores/chart-store.ts

### Hooks for US1

- [ ] T039 [P] [US1] Create useAnimation hook for entrance animations in frontend/src/hooks/use-animation.ts
- [ ] T040 [US1] Create useSentiment hook with React Query in frontend/src/hooks/use-sentiment.ts

### Chart Components for US1

- [ ] T041 [US1] Create SentimentChart wrapper for Lightweight Charts in frontend/src/components/charts/sentiment-chart.tsx
- [ ] T042 [US1] Create ChartCrosshair component with glowing indicator in frontend/src/components/charts/chart-crosshair.tsx
- [ ] T043 [US1] Create Sparkline component for mini previews in frontend/src/components/charts/sparkline.tsx

### Dashboard Components for US1

- [ ] T044 [US1] Create TickerInput with autocomplete in frontend/src/components/dashboard/ticker-input.tsx
- [ ] T045 [US1] Create TickerChip with animation support in frontend/src/components/dashboard/ticker-chip.tsx

### Layout Components for US1

- [ ] T046 [P] [US1] Create Header with logo and connection status in frontend/src/components/layout/header.tsx
- [ ] T047 [US1] Create PageTransition wrapper with Framer Motion in frontend/src/components/layout/page-transition.tsx

### Pages for US1

- [ ] T048 [US1] Create main dashboard page with chart and ticker input in frontend/src/app/(dashboard)/page.tsx
- [ ] T049 [US1] Create dashboard layout with header in frontend/src/app/(dashboard)/layout.tsx

### Unit Tests for US1

- [ ] T050 [P] [US1] Unit test for TickerInput autocomplete behavior in frontend/tests/unit/components/dashboard/ticker-input.test.tsx
- [ ] T051 [P] [US1] Unit test for animation store actions in frontend/tests/unit/stores/animation-store.test.ts
- [ ] T052 [P] [US1] Unit test for chart store scrub actions in frontend/tests/unit/stores/chart-store.test.ts

**Checkpoint**: User Story 1 complete - visitors see beautiful animated dashboard with sentiment chart

---

## Phase 4: User Story 2 - Gesture-Based Mobile Navigation (Priority: P2)

**Goal**: Swipe navigation between views with haptic feedback, bottom sheet for quick actions

**Independent Test**: Swipe left/right through Dashboard/Configs/Alerts/Settings, verify 60fps transitions with haptic feedback

### Zustand Stores for US2

- [ ] T053 [US2] Create view store with navigation and gesture state in frontend/src/stores/view-store.ts

### Hooks for US2

- [ ] T054 [US2] Create useGesture hook with swipe detection in frontend/src/hooks/use-gesture.ts

### Gesture Components for US2

- [ ] T055 [US2] Create SwipeView container with Framer Motion drag in frontend/src/components/gestures/swipe-view.tsx
- [ ] T056 [US2] Create PullToRefresh with threshold animation in frontend/src/components/gestures/pull-to-refresh.tsx
- [ ] T057 [US2] Create BottomSheet with edge swipe detection in frontend/src/components/gestures/bottom-sheet.tsx

### Navigation Components for US2

- [ ] T058 [US2] Create MobileNav with gesture hints in frontend/src/components/layout/mobile-nav.tsx
- [ ] T059 [US2] Create DesktopNav with tab buttons in frontend/src/components/layout/desktop-nav.tsx
- [ ] T060 [US2] Create QuickActions content for bottom sheet in frontend/src/components/dashboard/quick-actions.tsx

### Update Layout for US2

- [ ] T061 [US2] Update dashboard layout to use SwipeView navigation in frontend/src/app/(dashboard)/layout.tsx

### Unit Tests for US2

- [ ] T062 [P] [US2] Unit test for view store navigation actions in frontend/tests/unit/stores/view-store.test.ts
- [ ] T063 [P] [US2] Unit test for useGesture hook threshold logic in frontend/tests/unit/hooks/use-gesture.test.ts
- [ ] T064 [P] [US2] Unit test for SwipeView spring physics in frontend/tests/unit/components/gestures/swipe-view.test.tsx

**Checkpoint**: User Story 2 complete - mobile users can swipe between views with haptic feedback

---

## Phase 5: User Story 3 - Robinhood-Style Sentiment Charts (Priority: P3)

**Goal**: Interactive charts with touch scrubbing, gradient fills, glowing crosshair, smooth ticker switching

**Independent Test**: Load chart, scrub through time points, verify value display updates at 60fps with glowing indicator

### Chart Enhancements for US3

- [ ] T065 [US3] Add animated line drawing effect to SentimentChart in frontend/src/components/charts/sentiment-chart.tsx
- [ ] T066 [US3] Add gradient fill rendering to SentimentChart in frontend/src/components/charts/sentiment-chart.tsx
- [ ] T067 [US3] Create TickerSelector with animated switching in frontend/src/components/charts/ticker-selector.tsx
- [ ] T068 [US3] Add touch scrubbing with real-time value display in frontend/src/components/charts/sentiment-chart.tsx

### Hooks for US3

- [ ] T069 [US3] Create useChartScrub hook for touch/mouse handling in frontend/src/hooks/use-chart-scrub.ts

### Update Dashboard for US3

- [ ] T070 [US3] Update dashboard page with enhanced chart interactions in frontend/src/app/(dashboard)/page.tsx

### Unit Tests for US3

- [ ] T071 [P] [US3] Unit test for chart scrub hook position calculation in frontend/tests/unit/hooks/use-chart-scrub.test.ts
- [ ] T072 [P] [US3] Unit test for ticker switching animation in frontend/tests/unit/components/charts/ticker-selector.test.tsx

**Checkpoint**: User Story 3 complete - charts have Robinhood-style scrubbing and animations

---

## Phase 6: User Story 4 - Heat Map Visualization (Priority: P4)

**Goal**: Animated heat map matrix with Sources/Time toggle, color transitions, cell tooltips

**Independent Test**: Load config with 3+ tickers, toggle between Sources/Time views, verify smooth color transitions

### Heat Map Components for US4

- [ ] T073 [US4] Create HeatMap container with grid layout in frontend/src/components/charts/heat-map.tsx
- [ ] T074 [US4] Create HeatMapCell with color animation in frontend/src/components/charts/heat-map-cell.tsx
- [ ] T075 [US4] Create HeatMapToggle for Sources/Time views in frontend/src/components/charts/heat-map-toggle.tsx
- [ ] T076 [US4] Create HeatMapTooltip for cell details in frontend/src/components/charts/heat-map-tooltip.tsx
- [ ] T077 [US4] Create HeatMapLegend with color scale in frontend/src/components/charts/heat-map-legend.tsx

### Hooks for US4

- [ ] T078 [US4] Create useHeatMap hook with React Query in frontend/src/hooks/use-heatmap.ts

### Update Dashboard for US4

- [ ] T079 [US4] Add HeatMap section to dashboard page in frontend/src/app/(dashboard)/page.tsx

### Unit Tests for US4

- [ ] T080 [P] [US4] Unit test for HeatMapCell color transitions in frontend/tests/unit/components/charts/heat-map-cell.test.tsx
- [ ] T081 [P] [US4] Unit test for heat map toggle state in frontend/tests/unit/components/charts/heat-map-toggle.test.tsx

**Checkpoint**: User Story 4 complete - users can view sentiment across tickers in heat map format

---

## Phase 7: User Story 5 - Seamless Authentication Upgrade (Priority: P5)

**Goal**: Elegant auth modal with magic link and OAuth, celebratory success animation, data merge

**Independent Test**: Create anonymous config, tap "Save permanently", complete magic link auth, verify config persists with success animation

### Zustand Stores for US5

- [ ] T082 [US5] Create auth store with modal state and flow management in frontend/src/stores/auth-store.ts

### Hooks for US5

- [ ] T083 [US5] Create useAuth hook wrapping auth store in frontend/src/hooks/use-auth.ts

### Auth Components for US5

- [ ] T084 [US5] Create AuthModal with step animations in frontend/src/components/auth/auth-modal.tsx
- [ ] T085 [US5] Create MagicLinkForm with email validation in frontend/src/components/auth/magic-link-form.tsx
- [ ] T086 [US5] Create OAuthButtons with Google/GitHub in frontend/src/components/auth/oauth-buttons.tsx
- [ ] T087 [US5] Create SuccessAnimation with confetti/checkmark in frontend/src/components/auth/success-animation.tsx
- [ ] T088 [US5] Create CheckEmailAnimation with animated envelope in frontend/src/components/auth/check-email-animation.tsx
- [ ] T089 [US5] Create ErrorShake animation component in frontend/src/components/auth/error-shake.tsx

### Auth Pages for US5

- [ ] T090 [US5] Create magic link callback page in frontend/src/app/(auth)/callback/page.tsx
- [ ] T091 [US5] Create OAuth callback handler in frontend/src/app/(auth)/callback/oauth/page.tsx

### Update Dashboard for US5

- [ ] T092 [US5] Add "Save permanently" button triggering auth modal in frontend/src/app/(dashboard)/page.tsx

### Unit Tests for US5

- [ ] T093 [P] [US5] Unit test for auth store flow transitions in frontend/tests/unit/stores/auth-store.test.ts
- [ ] T094 [P] [US5] Unit test for MagicLinkForm validation in frontend/tests/unit/components/auth/magic-link-form.test.tsx
- [ ] T095 [P] [US5] Unit test for SuccessAnimation timing in frontend/tests/unit/components/auth/success-animation.test.tsx

**Checkpoint**: User Story 5 complete - anonymous users can upgrade to authenticated with beautiful flow

---

## Phase 8: User Story 6 - Real-Time Data Updates (Priority: P6)

**Goal**: SSE connection with countdown timer, pulse animations on updates, connection status indicator

**Independent Test**: Open dashboard, wait for 5-minute refresh, verify values pulse with glow animation

### SSE Infrastructure for US6

- [ ] T096 [US6] Create SSE client with reconnection logic in frontend/src/lib/api/sse.ts

### Hooks for US6

- [ ] T097 [US6] Create useSSE hook with React Query integration in frontend/src/hooks/use-sse.ts
- [ ] T098 [US6] Create useRefreshCountdown hook with timer logic in frontend/src/hooks/use-refresh-countdown.ts

### Components for US6

- [ ] T099 [US6] Create RefreshCountdown with circular progress in frontend/src/components/dashboard/refresh-countdown.tsx
- [ ] T100 [US6] Create ConnectionStatus indicator in frontend/src/components/dashboard/connection-status.tsx
- [ ] T101 [US6] Create GlowPulse animation wrapper in frontend/src/components/ui/glow-pulse.tsx

### Update Dashboard for US6

- [ ] T102 [US6] Add RefreshCountdown and ConnectionStatus to header in frontend/src/components/layout/header.tsx
- [ ] T103 [US6] Wrap updateable values with GlowPulse in frontend/src/app/(dashboard)/page.tsx

### Unit Tests for US6

- [ ] T104 [P] [US6] Unit test for SSE reconnection logic in frontend/tests/unit/lib/api/sse.test.ts
- [ ] T105 [P] [US6] Unit test for countdown timer accuracy in frontend/tests/unit/hooks/use-refresh-countdown.test.ts

**Checkpoint**: User Story 6 complete - dashboard updates in real-time with visual feedback

---

## Phase 9: User Story 7 - Configuration Management (Priority: P7)

**Goal**: Config cards with sparkline previews, create/edit modals, animated deletion

**Independent Test**: Create config, edit tickers, switch between configs, verify smooth animations

### Zustand Stores for US7

- [ ] T106 [US7] Create config store with CRUD operations in frontend/src/stores/config-store.ts

### Hooks for US7

- [ ] T107 [US7] Create useConfigs hook with React Query in frontend/src/hooks/use-configs.ts

### Components for US7

- [ ] T108 [US7] Create ConfigCard with sparkline preview in frontend/src/components/dashboard/config-card.tsx
- [ ] T109 [US7] Create ConfigForm modal for create/edit in frontend/src/components/dashboard/config-form.tsx
- [ ] T110 [US7] Create ConfigList with animated cards in frontend/src/components/dashboard/config-list.tsx
- [ ] T111 [US7] Create DeleteConfirmation with undo option in frontend/src/components/dashboard/delete-confirmation.tsx

### Pages for US7

- [ ] T112 [US7] Create configurations page in frontend/src/app/(dashboard)/configs/page.tsx

### Unit Tests for US7

- [ ] T113 [P] [US7] Unit test for config store CRUD actions in frontend/tests/unit/stores/config-store.test.ts
- [ ] T114 [P] [US7] Unit test for ConfigCard animation on delete in frontend/tests/unit/components/dashboard/config-card.test.tsx

**Checkpoint**: User Story 7 complete - users can manage their configurations with beautiful UI

---

## Phase 10: User Story 8 - Alert Setup & Management (Priority: P8)

**Goal**: Alert creation with threshold preview, toggle switches, trigger badges

**Independent Test**: Create sentiment alert for AAPL < -0.3, verify threshold preview, toggle on/off

### Hooks for US8

- [ ] T115 [US8] Create useAlerts hook with React Query in frontend/src/hooks/use-alerts.ts

### Components for US8

- [ ] T116 [US8] Create AlertCard with toggle switch in frontend/src/components/dashboard/alert-card.tsx
- [ ] T117 [US8] Create AlertForm with threshold slider in frontend/src/components/dashboard/alert-form.tsx
- [ ] T118 [US8] Create ThresholdPreview mini-chart in frontend/src/components/dashboard/threshold-preview.tsx
- [ ] T119 [US8] Create AlertList with quota display in frontend/src/components/dashboard/alert-list.tsx
- [ ] T120 [US8] Create TriggerBadge for recent alerts in frontend/src/components/dashboard/trigger-badge.tsx

### Pages for US8

- [ ] T121 [US8] Create alerts page in frontend/src/app/(dashboard)/alerts/page.tsx

### Unit Tests for US8

- [ ] T122 [P] [US8] Unit test for AlertCard toggle behavior in frontend/tests/unit/components/dashboard/alert-card.test.tsx
- [ ] T123 [P] [US8] Unit test for ThresholdPreview line positioning in frontend/tests/unit/components/dashboard/threshold-preview.test.tsx

**Checkpoint**: User Story 8 complete - users can create and manage alerts with visual threshold preview

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements affecting multiple user stories

### Settings Page

- [ ] T124 [P] Create Settings page with notification preferences in frontend/src/app/(dashboard)/settings/page.tsx
- [ ] T125 [P] Create NotificationPreferences component in frontend/src/components/dashboard/notification-preferences.tsx

### Error Handling

- [ ] T126 [P] Create ErrorBoundary with friendly fallback UI in frontend/src/components/ui/error-boundary.tsx
- [ ] T127 [P] Create OfflineBanner component in frontend/src/components/ui/offline-banner.tsx
- [ ] T128 [P] Create RateLimitMessage component in frontend/src/components/ui/rate-limit-message.tsx

### Accessibility

- [ ] T129 [P] Add keyboard navigation to all interactive elements
- [ ] T130 [P] Add ARIA labels to charts and heat map
- [ ] T131 [P] Test and fix color contrast issues

### Performance

- [ ] T132 [P] Add dynamic imports for chart components
- [ ] T133 [P] Add font preloading to document head
- [ ] T134 [P] Configure Next.js image optimization

### E2E Tests

- [ ] T135 [P] E2E test for first impression flow (landing → ticker → chart) in frontend/tests/e2e/dashboard.spec.ts
- [ ] T136 [P] E2E test for gesture navigation in frontend/tests/e2e/gestures.spec.ts
- [ ] T137 [P] E2E test for auth upgrade flow in frontend/tests/e2e/auth.spec.ts

### Documentation

- [ ] T138 Run quickstart.md validation and fix any setup issues
- [ ] T139 [P] Update CLAUDE.md with frontend patterns

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3-10 (User Stories) → Phase 11 (Polish)
                                              ↓
                                    Can run in parallel after Phase 2
```

### User Story Dependencies

All user stories depend ONLY on Phase 2 (Foundational). They can be implemented in parallel or sequentially:

| Story | Depends On | Can Start After |
|-------|------------|-----------------|
| US1 (P1) | Phase 2 | Phase 2 complete |
| US2 (P2) | Phase 2 | Phase 2 complete |
| US3 (P3) | Phase 2, US1 chart | US1 T041-T043 |
| US4 (P4) | Phase 2 | Phase 2 complete |
| US5 (P5) | Phase 2 | Phase 2 complete |
| US6 (P6) | Phase 2 | Phase 2 complete |
| US7 (P7) | Phase 2 | Phase 2 complete |
| US8 (P8) | Phase 2, US7 configs | US7 T106-T107 |

### Parallel Opportunities Within Phases

**Phase 2**: T011-T016 (types), T017-T022 (API clients), T024-T028 (utilities), T029-T030 (hooks), T034-T036 (tests) can all run in parallel

**Each User Story**: Tests, models, and independent components can run in parallel within the story

---

## Parallel Example: Phase 2 Foundation

```bash
# Launch all type definitions in parallel:
Task: "Create sentiment types in frontend/src/types/sentiment.ts"
Task: "Create config types in frontend/src/types/config.ts"
Task: "Create auth types in frontend/src/types/auth.ts"
Task: "Create alert types in frontend/src/types/alert.ts"

# Launch all API clients in parallel:
Task: "Create auth API client in frontend/src/lib/api/auth.ts"
Task: "Create configs API client in frontend/src/lib/api/configs.ts"
Task: "Create sentiment API client in frontend/src/lib/api/sentiment.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (~10 tasks)
2. Complete Phase 2: Foundational (~26 tasks)
3. Complete Phase 3: User Story 1 (~16 tasks)
4. **STOP and VALIDATE**: Test independently
5. Deploy to Amplify for demo

**MVP Total**: ~52 tasks

### Incremental Delivery

| Increment | Stories Included | Cumulative Value |
|-----------|-----------------|------------------|
| MVP | US1 | Beautiful chart with ticker input |
| +Gestures | US1, US2 | Mobile-native navigation |
| +Charts | US1-US3 | Full Robinhood-style charts |
| +HeatMap | US1-US4 | Portfolio overview visualization |
| +Auth | US1-US5 | User accounts, persistent data |
| +Real-time | US1-US6 | Live updates, connection status |
| +Configs | US1-US7 | Multiple configurations |
| +Alerts | US1-US8 | Notifications, re-engagement |

### Suggested MVP Scope

**User Story 1 only** delivers:
- Dark fintech theme with cyan accents
- Ticker input with autocomplete
- Animated sentiment chart
- Haptic feedback on mobile
- Pull-to-refresh

This is enough to validate the "wow factor" hypothesis before building more features.

---

## Summary

| Category | Count |
|----------|-------|
| **Total Tasks** | 139 |
| Setup (Phase 1) | 10 |
| Foundational (Phase 2) | 26 |
| US1 - First Impression | 16 |
| US2 - Gestures | 12 |
| US3 - Charts | 8 |
| US4 - Heat Map | 9 |
| US5 - Authentication | 14 |
| US6 - Real-Time | 10 |
| US7 - Config Management | 9 |
| US8 - Alerts | 9 |
| Polish (Phase 11) | 16 |
| **Parallelizable [P]** | 72 (52%) |

---

## Notes

- All file paths are relative to `frontend/` directory
- [P] tasks can run in parallel within their phase
- [Story] label traces task to user story for independent testing
- Constitution requires 80%+ test coverage - tests included per story
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
