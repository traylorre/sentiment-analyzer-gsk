# Feature Specification: Sentiment Dashboard Frontend

**Feature Branch**: `007-sentiment-dashboard-frontend`
**Created**: 2025-11-27
**Status**: Draft
**Input**: Mobile-first, gesture-based frontend dashboard for the Financial News Sentiment Analyzer (Feature 006). Dark fintech aesthetic with cyan accents. Target: <200ms interactions, Robinhood-style UI. Polish-first approach prioritizing exceptional UX and 60fps animations over feature count.

## Relationship to Feature 006

This frontend specification is the **client-side companion** to Feature 006 (Financial News Sentiment & Asset Volatility Dashboard). Feature 006 defines the backend API contracts, authentication flows, and data models. This specification defines the user interface that consumes those APIs.

**Backend Dependencies** (from Feature 006):
- Dashboard API (`/api/v2/configurations`, `/api/v2/sentiment`, `/api/v2/volatility`)
- Auth API (`/api/v2/auth/*` - anonymous, magic link, OAuth)
- Notification API (`/api/v2/alerts`, `/api/v2/notifications`)
- SSE endpoint for real-time updates

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First Impression & Instant Value (Priority: P1)

A potential user discovers the dashboard for the first time. Without any signup friction, they immediately experience a beautiful, dark-themed interface with smooth animations. They enter stock tickers (with autocomplete), select a timeframe, and within seconds see an elegant Robinhood-style sentiment chart with buttery-smooth animations. The entire experience feels premium and responsive, with every interaction providing satisfying haptic feedback on mobile.

**Why this priority**: First impressions determine user retention. The "wow factor" of beautiful animations and instant responsiveness creates emotional investment before any account creation. This is the hook that converts visitors to users.

**Independent Test**: Can be tested by loading the dashboard on a mobile device, entering "AAPL", and verifying the chart renders with smooth 60fps animations within 3 seconds, with haptic feedback on each tap.

**Acceptance Scenarios**:

1. **Given** a new visitor on any device, **When** they land on the dashboard, **Then** they see a dark, premium interface with a glowing cyan accent and smooth entrance animations completing within 500ms
2. **Given** a user taps the ticker input, **When** they type "AA", **Then** autocomplete suggestions appear within 200ms with a subtle slide-in animation
3. **Given** a user selects a ticker, **When** the sentiment chart loads, **Then** it renders with a Robinhood-style line animation (drawing from left to right) completing within 1 second
4. **Given** a user on mobile, **When** they tap any interactive element, **Then** they feel haptic feedback (subtle vibration) confirming the interaction
5. **Given** a user pulls down on the dashboard, **When** the pull exceeds the threshold, **Then** they see a refresh animation and feel haptic feedback, with data refreshing within 2 seconds

---

### User Story 2 - Gesture-Based Mobile Navigation (Priority: P2)

A returning mobile user navigates the dashboard entirely through gestures. They swipe horizontally to move between Dashboard, Configurations, Alerts, and Settings views. Each swipe triggers haptic feedback and smooth page transitions. They pull up from the bottom to reveal a quick-actions sheet for common tasks like "Add Ticker" or "Create Alert".

**Why this priority**: Mobile-first means gestures are primary navigation. This differentiates from competitors and creates muscle-memory engagement. Desktop users get traditional navigation, but mobile users get a native-app-like experience.

**Independent Test**: Can be tested by swiping left/right through all four main views on a mobile device, verifying each transition is smooth (60fps) and includes haptic feedback.

**Acceptance Scenarios**:

1. **Given** a user on the Dashboard view, **When** they swipe left, **Then** the view smoothly transitions to Configurations with a parallax effect completing within 300ms
2. **Given** a user is swiping between views, **When** the swipe is incomplete (< 30% of screen width), **Then** the view bounces back to original position with spring physics
3. **Given** a user on any view, **When** they swipe up from the bottom edge, **Then** a bottom sheet appears with quick actions (Add Ticker, Create Alert, Refresh Data)
4. **Given** a user on mobile, **When** any gesture completes, **Then** they feel appropriate haptic feedback (light for navigation, medium for actions)
5. **Given** a user on desktop, **When** they interact with the dashboard, **Then** they see traditional tab/button navigation instead of gesture prompts

---

### User Story 3 - Robinhood-Style Sentiment Charts (Priority: P3)

A user views detailed sentiment data through beautiful, interactive charts. The chart displays sentiment scores over time with a smooth, animated line that responds to touch/mouse. Users can scrub through time by dragging, with the current value updating in real-time. The chart includes subtle gradients, glowing effects on the active point, and smooth transitions when switching between tickers.

**Why this priority**: Charts are the core data visualization. Robinhood's chart UX is the gold standard for financial apps - it creates emotional connection to data through beautiful, responsive visualizations. This directly impacts user engagement and retention.

**Independent Test**: Can be tested by loading a sentiment chart, scrubbing through time points, and verifying the value display updates at 60fps with a glowing indicator following the touch/cursor.

**Acceptance Scenarios**:

1. **Given** a user views a sentiment chart, **When** the chart loads, **Then** the line animates from left to right with a gradient fill below, completing within 800ms
2. **Given** a user touches/hovers on the chart, **When** they drag horizontally, **Then** a glowing crosshair follows their position with the exact sentiment value displayed above
3. **Given** a user is scrubbing the chart, **When** they lift their finger/release mouse, **Then** the display smoothly animates to the latest value with spring physics
4. **Given** a user switches between tickers, **When** the new data loads, **Then** the old chart fades out and the new one animates in with a smooth crossfade (300ms)
5. **Given** market sentiment changes, **When** new data arrives via real-time updates, **Then** the chart line smoothly extends/updates without jarring redraws

---

### User Story 4 - Heat Map Visualization (Priority: P4)

A user views the heat map matrix to compare sentiment across multiple tickers and sources. The heat map displays a grid with beautiful color gradients (red for bearish, yellow for neutral, green for bullish) with smooth transitions when data updates. Users can toggle between "Sources" view (Tiingo vs Finnhub vs Our Model) and "Time Periods" view (Today vs 1W vs 1M vs 3M).

**Why this priority**: Heat maps provide at-a-glance portfolio overview. This is the "power user" visualization that differentiates from basic dashboards. The visual polish here reinforces the premium feel established in P1-P3.

**Independent Test**: Can be tested by loading a configuration with 3+ tickers, viewing the heat map, and toggling between Sources/Time views, verifying smooth color transitions and view switches.

**Acceptance Scenarios**:

1. **Given** a user views the heat map, **When** it loads, **Then** cells fade in sequentially (staggered animation) from top-left to bottom-right over 500ms
2. **Given** a user toggles between Sources and Time Periods view, **When** the toggle is tapped, **Then** cells cross-fade to new colors over 300ms with a subtle scale animation
3. **Given** sentiment data updates, **When** a cell's score changes, **Then** the cell color smoothly transitions to the new color over 400ms
4. **Given** a user taps a heat map cell, **When** the tap is registered, **Then** a detail tooltip appears with the exact score, source, and timestamp
5. **Given** a user views on mobile, **When** the heat map is too wide, **Then** it becomes horizontally scrollable with momentum scrolling and edge shadows

---

### User Story 5 - Seamless Authentication Upgrade (Priority: P5)

An anonymous user who has been exploring decides to save their configuration. They tap "Save permanently" and choose between magic link (email) or social login (Google/GitHub). The entire flow happens within the app via elegant modal overlays - no jarring redirects. After authentication, their anonymous data seamlessly merges with their new account, and they see a celebratory animation confirming success.

**Why this priority**: Authentication is the conversion point from visitor to user. A frictionless, beautiful auth experience directly impacts conversion rates. The "celebration" moment creates positive emotional association.

**Independent Test**: Can be tested by creating an anonymous configuration, tapping "Save permanently", completing magic link authentication, and verifying the configuration persists and a success animation plays.

**Acceptance Scenarios**:

1. **Given** an anonymous user with saved config, **When** they tap "Save permanently", **Then** an elegant modal slides up with auth options (email, Google, GitHub) with staggered entrance animations
2. **Given** a user selects magic link, **When** they enter email and submit, **Then** they see a beautiful "check your email" animation with a mail icon that animates
3. **Given** a user clicks the magic link from email, **When** authentication succeeds, **Then** they return to the app and see a celebratory animation (confetti burst or checkmark scale-up)
4. **Given** a user selects Google/GitHub, **When** OAuth completes, **Then** the modal smoothly dismisses and a success toast slides in from the top
5. **Given** authentication fails, **When** error occurs, **Then** the modal shows a gentle shake animation with a friendly error message, not a jarring alert

---

### User Story 6 - Real-Time Data Updates (Priority: P6)

A user leaves the dashboard open and sees data update in real-time. A subtle countdown timer shows "Refreshing in 4:32" with a circular progress indicator. When new data arrives, affected elements pulse with a subtle glow to draw attention. Users can also tap "Refresh Now" for immediate updates with a satisfying pull-to-refresh animation.

**Why this priority**: Real-time updates create "stickiness" - users keep the app open. The visual feedback for updates reinforces that the app is "alive" and working. This builds trust and engagement.

**Independent Test**: Can be tested by opening the dashboard, waiting for the 5-minute auto-refresh, and verifying updated values pulse with a glow animation without page reload.

**Acceptance Scenarios**:

1. **Given** a user is viewing the dashboard, **When** they look at the refresh indicator, **Then** they see a circular countdown with "Next refresh in X:XX" that smoothly decrements
2. **Given** the countdown reaches zero, **When** new data arrives, **Then** updated values pulse with a cyan glow animation (2 pulses over 1 second)
3. **Given** a user taps "Refresh Now", **When** the button is tapped, **Then** the refresh icon spins and the countdown resets with a satisfying animation
4. **Given** data is being fetched, **When** the request is in progress, **Then** a subtle loading shimmer appears on affected components (skeleton loading)
5. **Given** a refresh fails, **When** error occurs, **Then** the countdown shows "Retry in 30s" with the last successful update time displayed

---

### User Story 7 - Configuration Management (Priority: P7)

A user manages their saved configurations through a beautiful interface. They can create new configurations (up to 2), edit existing ones, and delete with confirmation. Each configuration is displayed as an elegant card with a mini-preview of the sentiment trend. Switching between configurations uses smooth card-swapping animations.

**Why this priority**: Configuration management is essential for power users but not for first-time visitors. The UI must be functional but also maintain the premium aesthetic established earlier.

**Independent Test**: Can be tested by creating a configuration, editing its tickers, then switching between two configurations, verifying smooth transitions and card animations.

**Acceptance Scenarios**:

1. **Given** a user views Configurations, **When** they see their saved configs, **Then** each appears as a card with name, ticker count, and mini sparkline chart
2. **Given** a user taps "New Configuration", **When** the creation flow starts, **Then** a modal slides up with a beautiful form featuring floating labels and smooth focus animations
3. **Given** a user edits a configuration, **When** they add/remove tickers, **Then** the ticker chips animate in/out with scale+fade transitions
4. **Given** a user deletes a configuration, **When** they confirm deletion, **Then** the card shrinks and fades out with a satisfying animation
5. **Given** a user taps to switch configurations, **When** the switch occurs, **Then** the dashboard view smoothly cross-fades to the new configuration's data

---

### User Story 8 - Alert Setup & Management (Priority: P8)

An authenticated user sets up sentiment and volatility alerts. The alert creation flow guides them through threshold selection with a visual slider that shows the alert zone on a mini-chart preview. Active alerts display as compact cards with toggle switches for quick enable/disable.

**Why this priority**: Alerts drive re-engagement and email opens. While important for retention, users typically set up alerts after exploring the core dashboard features.

**Independent Test**: Can be tested by creating a sentiment alert for AAPL below -0.3, verifying the threshold preview animates on the mini-chart, and toggling the alert on/off.

**Acceptance Scenarios**:

1. **Given** a user creates an alert, **When** they drag the threshold slider, **Then** a mini-chart shows the threshold line moving with the slider in real-time
2. **Given** a user sets a threshold, **When** the value is set, **Then** the threshold line pulses briefly to confirm the selection
3. **Given** a user views their alerts, **When** the list loads, **Then** alerts appear as compact cards with ticker, type, threshold, and a toggle switch
4. **Given** a user toggles an alert off, **When** the toggle animates, **Then** the card visually dims (opacity reduction) to indicate inactive status
5. **Given** an alert is triggered, **When** notification is received, **Then** the alert card shows a badge indicating recent trigger

---

### Edge Cases

- **Slow network**: Show skeleton loading states with shimmer animations; never show blank screens
- **Offline mode**: Display "You're offline" banner with last-synced timestamp; disable refresh buttons
- **Invalid ticker**: Show inline error with red highlight and shake animation; suggest corrections
- **API rate limited**: Show friendly "Taking a breather" message with retry countdown
- **Chart data gaps**: Display dashed line segments for missing data periods with "No data" labels
- **Authentication timeout**: Show re-auth modal overlay without losing current view/data
- **Very long ticker lists**: Virtualize scrolling for performance; maintain 60fps
- **Gesture conflicts**: Bottom sheet should not conflict with pull-to-refresh; use edge detection
- **Color blindness**: Heat map colors must work with deuteranopia; include value labels
- **Reduced motion**: Respect prefers-reduced-motion; provide instant transitions as alternative

---

## Requirements *(mandatory)*

### Functional Requirements

**Visual Design & Animation**
- **FR-001**: System MUST display a dark theme with cyan (#00FFFF) accent colors as the default and only theme
- **FR-002**: All interactive elements MUST provide visual feedback within 100ms of user input
- **FR-003**: Page transitions MUST complete within 300ms at 60fps
- **FR-004**: Chart animations MUST render at 60fps on devices from 2020 onwards
- **FR-005**: System MUST include entrance animations for all major UI components (staggered fade-in)
- **FR-006**: Color gradients for sentiment MUST use red (#EF4444) for negative, yellow (#EAB308) for neutral, green (#22C55E) for positive

**Mobile Gestures**
- **FR-007**: System MUST support horizontal swipe navigation between main views (Dashboard, Configurations, Alerts, Settings)
- **FR-008**: Swipe gestures MUST include haptic feedback on mobile devices that support it
- **FR-009**: Pull-to-refresh MUST be available on all data views with visual progress indicator
- **FR-010**: Bottom sheet MUST be accessible via upward swipe from screen bottom edge
- **FR-011**: Incomplete swipes (< 30% of threshold) MUST spring back with physics-based animation
- **FR-012**: System MUST detect device type and show appropriate navigation (gestures for mobile, tabs for desktop)

**Charts & Data Visualization**
- **FR-013**: Sentiment charts MUST display as interactive line charts with gradient fill below the line
- **FR-014**: Charts MUST support touch/mouse scrubbing with real-time value display
- **FR-015**: Active data point MUST display with a glowing indicator that follows user input
- **FR-016**: Heat map MUST display a matrix grid with smooth color transitions between states
- **FR-017**: Heat map MUST support toggling between Sources view and Time Periods view
- **FR-018**: Heat map cells MUST display exact values on tap/hover via tooltip

**Real-Time Updates**
- **FR-019**: Dashboard MUST display a countdown timer showing time until next auto-refresh (5-minute interval)
- **FR-020**: Updated data MUST be highlighted with a pulse animation to draw user attention
- **FR-021**: Manual refresh MUST be available via button tap or pull-to-refresh gesture
- **FR-022**: System MUST maintain persistent connection for real-time data streaming
- **FR-023**: Connection status MUST be visually indicated (connected/reconnecting/offline)

**Authentication Flow**
- **FR-024**: Anonymous users MUST be able to use the dashboard without authentication
- **FR-025**: Authentication upgrade MUST be available via modal overlay (no page navigation)
- **FR-026**: System MUST support magic link (email) authentication
- **FR-027**: System MUST support OAuth authentication (Google, GitHub)
- **FR-028**: Successful authentication MUST display a celebratory animation
- **FR-029**: Authentication errors MUST display with gentle shake animation and friendly message
- **FR-030**: Anonymous data MUST merge seamlessly into authenticated account

**Configuration Management**
- **FR-031**: Users MUST be able to create up to 2 configurations (matching backend limit)
- **FR-032**: Configuration cards MUST display name, ticker count, and mini sparkline preview
- **FR-033**: Configuration switching MUST use smooth cross-fade animation
- **FR-034**: Ticker input MUST provide autocomplete with suggestions appearing within 200ms
- **FR-035**: Configuration deletion MUST require confirmation with undo option (5 seconds)

**Alert Management**
- **FR-036**: Alert creation MUST include visual threshold preview on mini-chart
- **FR-037**: Alert cards MUST display toggle switch for quick enable/disable
- **FR-038**: Disabled alerts MUST display with reduced opacity visual treatment
- **FR-039**: System MUST display daily email quota status (X of 10 used)

**Responsive Design**
- **FR-040**: Interface MUST be fully functional from 320px to 2560px screen width
- **FR-041**: Mobile layout MUST prioritize vertical scrolling with gesture navigation
- **FR-042**: Desktop layout MUST display side-by-side panels where appropriate
- **FR-043**: Touch targets MUST be minimum 44x44 pixels on mobile

**Accessibility**
- **FR-044**: System MUST respect prefers-reduced-motion system setting
- **FR-045**: Heat map MUST include text labels for color-blind accessibility
- **FR-046**: All interactive elements MUST be keyboard accessible on desktop
- **FR-047**: System MUST maintain sufficient color contrast (WCAG AA minimum)

**Performance**
- **FR-048**: Initial page load MUST display meaningful content within 3 seconds on 3G
- **FR-049**: User interactions MUST feel responsive within 200ms
- **FR-050**: Chart rendering MUST not block main thread for more than 50ms

### Key Entities

- **View State**: Current active view (Dashboard, Configurations, Alerts, Settings) and transition progress
- **Theme State**: Color palette configuration, animation preferences, haptic settings
- **Chart State**: Current ticker, timeframe, scrub position, zoom level
- **Auth State**: Anonymous/authenticated status, tokens, user profile
- **Configuration Cache**: Local cache of configurations with last-sync timestamp
- **Animation Queue**: Pending animations with priority for smooth sequencing
- **Gesture State**: Current gesture type, progress, and target action

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

**Performance Metrics**
- **SC-001**: 95% of user interactions receive visual feedback within 200ms
- **SC-002**: Chart animations maintain 60fps on 90% of devices tested
- **SC-003**: Initial meaningful content displays within 3 seconds on 3G connection
- **SC-004**: Page transitions complete within 300ms for 95th percentile

**User Experience Metrics**
- **SC-005**: 80% of mobile users successfully navigate using gestures on first session
- **SC-006**: Anonymous-to-authenticated conversion rate of 30% within first week
- **SC-007**: Users rate visual design 4+ stars (out of 5) in feedback surveys
- **SC-008**: Task completion rate of 90% for "create configuration and view sentiment"

**Engagement Metrics**
- **SC-009**: Average session duration of 3+ minutes for returning users
- **SC-010**: 70% of users interact with chart scrubbing feature during first session
- **SC-011**: 50% of authenticated users create at least one alert

**Accessibility Metrics**
- **SC-012**: Interface passes WCAG 2.1 AA automated testing
- **SC-013**: All primary flows completable via keyboard on desktop

**Quality Metrics**
- **SC-014**: Zero critical UI bugs reported in first 30 days post-launch
- **SC-015**: Lighthouse performance score of 90+ on mobile

---

## Assumptions

- Users have devices from 2020 or later capable of smooth 60fps animations
- Backend API endpoints (Feature 006) are available and functional
- Users accept dark theme as the only option (no light theme)
- Haptic feedback API is available on modern mobile browsers (with graceful degradation)
- Users are familiar with swipe gestures from native mobile apps
- 3G network speed is the baseline for performance testing
- Real-time updates via SSE are supported by the backend
- OAuth providers (Google, GitHub) are configured in backend Cognito
- SendGrid magic link emails are configured and working
- Maximum 2 configurations per user (backend enforced limit)
- Maximum 5 tickers per configuration (backend enforced limit)

---

## Dependencies

- Feature 006 backend API contracts (Dashboard API, Auth API, Notification API)
- AWS Cognito for OAuth authentication
- SendGrid for magic link emails
- Tiingo and Finnhub for sentiment data (via backend)
- SSE endpoint for real-time updates

---

## Out of Scope

- Progressive Web App (PWA) functionality
- Keyboard shortcuts
- Light theme / theme switching
- Offline data caching beyond basic error handling
- Push notifications (email only per Feature 006)
- Premium tier features (5+ configs, longer history)
- Contributor/Operator/Admin role interfaces
- Alert template gallery
- Historical replay feature
- Sector benchmark comparisons
