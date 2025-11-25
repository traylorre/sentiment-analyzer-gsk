# Feature Specification: Mobile-First Sentiment Dashboard (POWERPLAN)

**Branch**: `002-mobile-sentiment-dashboard`
**Created**: 2025-11-25
**Status**: Draft
**Codename**: POWERPLAN

## Purpose

Deliver a stunning, mobile-first sentiment analysis dashboard that transforms raw news data into beautiful, interactive visualizations. Users can track sentiment trends across 5 custom topics with real-time updates, historical analysis, and an immersive experience that delights on every interaction.

## Demo Success Criteria

**The "Wow" Moments:**
1. User opens dashboard on phone → Sees elegant, responsive interface instantly
2. User enters 5 tags → Animated chips appear with satisfying haptic feedback
3. User selects time range → Historical data backfills with smooth progress animation
4. Dashboard pulses gently → Shows real-time data freshness ("alive" feeling)
5. Sentiment Mood Ring → Beautiful gradient visualization of overall sentiment
6. Swipe between tags → Fluid transitions with trend sparklines
7. Pull-to-refresh → Satisfying animation with new data appearing
8. Optional ambient audio → Subtle soundscape matching sentiment mood

---

## User Scenarios & Testing

### User Story 1 - Tag Selection & Search (Priority: P1)

A user opens the dashboard and wants to track sentiment for specific topics they care about.

**Why this priority**: Core functionality - everything else depends on being able to select what to track.

**Independent Test**: User can add 5 tags, see them displayed as chips, and remove/edit them.

**Acceptance Scenarios**:

1. **Given** the dashboard is open, **When** user taps "Add Topic", **Then** a sleek input modal appears with keyboard auto-focused
2. **Given** user is typing a tag, **When** they type 3+ characters, **Then** autocomplete suggestions appear from trending topics
3. **Given** user has entered a tag, **When** they tap "Add" or press Enter, **Then** an animated chip appears with gentle haptic feedback
4. **Given** user has 5 tags, **When** they try to add a 6th, **Then** system shows "Maximum 5 topics" with option to replace one
5. **Given** user has tags selected, **When** they long-press a chip, **Then** delete option appears with swipe-to-delete gesture

---

### User Story 2 - Time Range & Historical Data (Priority: P1)

A user wants to see sentiment trends over a specific time period, potentially backfilling historical data.

**Why this priority**: Historical context is essential for understanding trends, not just current state.

**Independent Test**: User can select time range and see data populated for that period.

**Acceptance Scenarios**:

1. **Given** dashboard is loaded, **When** user taps time picker, **Then** elegant bottom sheet shows: "Past 24h", "Past Week", "Past Month", "Custom Range"
2. **Given** user selects "Past Week", **When** DynamoDB has data for that period, **Then** charts animate in with data from that range
3. **Given** user selects "Past Month", **When** DynamoDB lacks historical data, **Then** system offers "Backfill historical data?" with progress indicator
4. **Given** backfill is requested, **When** Ingestion Lambda fetches historical NewsAPI data, **Then** progress bar shows "Loading: 45 of 200 articles..."
5. **Given** time range is active, **When** new data arrives in real-time, **Then** it smoothly animates into existing charts

---

### User Story 3 - Sentiment Mood Ring Visualization (Priority: P1)

A user wants to see the overall sentiment at a glance through an intuitive, beautiful visualization.

**Why this priority**: The "hero" visualization that makes the dashboard memorable and instantly communicates sentiment.

**Independent Test**: User sees a circular visualization that accurately reflects aggregate sentiment.

**Acceptance Scenarios**:

1. **Given** data is loaded, **When** dashboard renders, **Then** Mood Ring displays with smooth gradient: Red (negative) → Yellow (neutral) → Green (positive)
2. **Given** sentiment is 70% positive, **When** viewing Mood Ring, **Then** ring is predominantly green with subtle yellow/red segments
3. **Given** user taps Mood Ring center, **When** detail view opens, **Then** breakdown shows: "Positive: 70%, Neutral: 20%, Negative: 10%"
4. **Given** new data arrives, **When** sentiment shifts, **Then** Mood Ring smoothly animates to new position (not jarring jumps)
5. **Given** user is viewing Mood Ring, **When** they rotate phone to landscape, **Then** visualization expands elegantly to fill space

---

### User Story 4 - Real-Time Pulse Animation (Priority: P2)

A user wants to feel that the dashboard is "alive" and showing fresh data.

**Why this priority**: Creates emotional connection and trust that data is current.

**Independent Test**: Dashboard shows visual indicator of data freshness and update frequency.

**Acceptance Scenarios**:

1. **Given** dashboard is active, **When** data stream is healthy, **Then** subtle pulse animation plays every 5 seconds
2. **Given** new article is ingested, **When** it appears in dashboard, **Then** pulse quickens momentarily (heartbeat effect)
3. **Given** high ingestion rate (>10 items/min), **When** viewing dashboard, **Then** pulse is faster, showing activity
4. **Given** no new data for 5 minutes, **When** viewing dashboard, **Then** pulse slows and "Last updated: 5m ago" appears
5. **Given** connection lost, **When** data stops flowing, **Then** pulse stops and "Reconnecting..." indicator shows

---

### User Story 5 - Trend Sparklines (Priority: P2)

A user wants to see how sentiment has changed over time for each topic.

**Why this priority**: Trends tell the story - is sentiment improving or declining?

**Independent Test**: Each tag shows a mini chart of sentiment trajectory.

**Acceptance Scenarios**:

1. **Given** tag chips are displayed, **When** sufficient data exists, **Then** each chip shows a sparkline below the label
2. **Given** sparkline shows upward trend, **When** user views it, **Then** line is green with "↑" indicator
3. **Given** sparkline shows downward trend, **When** user views it, **Then** line is red with "↓" indicator
4. **Given** user taps a sparkline, **When** detail view opens, **Then** full-size chart with data points appears
5. **Given** user swipes left/right on sparklines, **When** comparing tags, **Then** smooth transition between tag details

---

### User Story 6 - Article Cards with Sentiment Badges (Priority: P2)

A user wants to see individual articles that contribute to the sentiment score.

**Why this priority**: Transparency - users can verify why sentiment scores are what they are.

**Independent Test**: User can browse recent articles with visible sentiment indicators.

**Acceptance Scenarios**:

1. **Given** articles exist in DynamoDB, **When** scrolling article feed, **Then** cards show: headline, source, time, sentiment badge
2. **Given** article has positive sentiment, **When** viewing card, **Then** green badge shows "Positive (0.85)"
3. **Given** user taps article card, **When** detail expands, **Then** shows: full snippet, matched tags, "Why this sentiment?" explanation
4. **Given** user swipes article left, **When** gesture completes, **Then** article is dismissed with "Hide" action
5. **Given** user filters by sentiment, **When** selecting "Negative only", **Then** feed shows only negative articles

---

### User Story 7 - Micro-Interactions & Haptics (Priority: P2)

A user expects a premium, tactile experience on mobile.

**Why this priority**: Polish that elevates the experience from "app" to "premium product".

**Independent Test**: Interactions feel responsive and satisfying.

**Acceptance Scenarios**:

1. **Given** user adds a tag, **When** chip animates in, **Then** device vibrates gently (haptic feedback)
2. **Given** user pulls to refresh, **When** threshold is reached, **Then** stronger haptic pulse signals "release to refresh"
3. **Given** user navigates between views, **When** transition plays, **Then** subtle haptic accompanies the motion
4. **Given** sentiment changes significantly, **When** alert appears, **Then** distinct haptic pattern draws attention
5. **Given** user is on iOS/Android, **When** using haptics, **Then** system uses native haptic APIs for best feel

---

### User Story 8 - Ambient Audio (Priority: P3)

A user wants an immersive experience with optional background audio that reflects sentiment.

**Why this priority**: Differentiator feature - unique and memorable, but not essential.

**Independent Test**: User can enable/disable audio that changes based on sentiment.

**Acceptance Scenarios**:

1. **Given** user opens settings, **When** toggling "Ambient Audio", **Then** audio fades in/out smoothly
2. **Given** audio is enabled and sentiment is positive, **When** viewing dashboard, **Then** upbeat, calm tones play
3. **Given** sentiment shifts to negative, **When** audio is enabled, **Then** tones become more somber/tense
4. **Given** user adjusts volume slider, **When** moving slider, **Then** audio volume changes in real-time
5. **Given** user leaves app, **When** app goes to background, **Then** audio pauses automatically

---

### User Story 9 - Comparative View (Priority: P2)

A user wants to compare sentiment across their 5 topics side-by-side.

**Why this priority**: The power of tracking multiple topics is comparing them.

**Independent Test**: User can see all 5 topics compared in a single view.

**Acceptance Scenarios**:

1. **Given** 5 tags are selected, **When** user taps "Compare", **Then** horizontal bar chart shows all 5 sentiments
2. **Given** comparative view is open, **When** viewing bars, **Then** each bar is color-coded by sentiment (red/yellow/green)
3. **Given** user taps a bar, **When** detail appears, **Then** shows: "AI: 72% positive (↑5% from yesterday)"
4. **Given** user toggles "Show Trend", **When** enabled, **Then** each bar shows mini sparkline beside it
5. **Given** user wants to share, **When** tapping share icon, **Then** generates shareable image of comparison

---

### User Story 10 - Stats Dashboard (Priority: P2)

A user wants to see key metrics and statistics at a glance.

**Why this priority**: Data-driven users want numbers, not just visualizations.

**Independent Test**: User can view aggregate statistics for their selected topics.

**Acceptance Scenarios**:

1. **Given** data is loaded, **When** viewing stats panel, **Then** shows: Total Articles, Avg Sentiment, Most Active Topic
2. **Given** stats panel is visible, **When** viewing "Top Keywords", **Then** word cloud or list shows driving terms
3. **Given** user views "Most Polarizing", **When** tapping, **Then** shows articles with highest sentiment variance
4. **Given** stats refresh, **When** numbers change, **Then** animated counter ticks up/down to new value
5. **Given** user exports stats, **When** tapping "Export", **Then** generates CSV or shareable summary

---

## Edge Cases

- What happens when no data exists for a selected time range? → Show "No data yet" with option to backfill
- What happens when NewsAPI rate limit is hit during backfill? → Show progress, resume when limit resets
- What happens when user has 0 tags selected? → Show onboarding prompt: "Add your first topic"
- What happens when all sentiment is neutral? → Mood Ring shows yellow, messaging explains low variance
- What happens on very slow connections? → Skeleton loaders, offline indicator, cached data fallback
- What happens when DynamoDB is throttled? → Graceful degradation, show cached data, retry with backoff

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST allow users to select exactly 1-5 topic tags
- **FR-002**: System MUST display sentiment as Mood Ring visualization
- **FR-003**: System MUST support time range selection (24h, week, month, custom)
- **FR-004**: System MUST show real-time updates via SSE or polling
- **FR-005**: System MUST display trend sparklines for each topic
- **FR-006**: System MUST show article cards with sentiment badges
- **FR-007**: System MUST provide haptic feedback on mobile interactions
- **FR-008**: System MAY provide optional ambient audio based on sentiment
- **FR-009**: System MUST support pull-to-refresh gesture
- **FR-010**: System MUST work offline with cached data
- **FR-011**: System MUST support historical data backfill on demand
- **FR-012**: System MUST provide comparative view of all topics

### Non-Functional Requirements

- **NFR-001**: Dashboard MUST load in < 2 seconds on 4G connection
- **NFR-002**: Animations MUST run at 60fps on mid-tier devices
- **NFR-003**: Dashboard MUST be responsive from 320px to 1440px width
- **NFR-004**: Dashboard MUST support dark mode and light mode
- **NFR-005**: Dashboard MUST be accessible (WCAG 2.1 AA)
- **NFR-006**: Dashboard MUST work on iOS Safari and Android Chrome

### Key Entities

- **Topic Tag**: User-selected keyword to track (max 5)
- **Sentiment Score**: Float 0.0-1.0 with classification (positive/neutral/negative)
- **Article**: News item with headline, snippet, source, timestamp, sentiment
- **Time Range**: Selected period for data display (start/end timestamps)
- **User Preferences**: Audio enabled, theme, notification settings

---

## Technical Approach

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Mobile Client (PWA/Native)                    │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │ Tag     │  │ Mood    │  │ Trend   │  │ Article │           │
│  │ Selector│  │ Ring    │  │ Charts  │  │ Feed    │           │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘           │
│       │            │            │            │                  │
│  ┌────┴────────────┴────────────┴────────────┴────┐            │
│  │              State Management (Zustand)         │            │
│  └────────────────────────┬────────────────────────┘            │
│                           │                                      │
│  ┌────────────────────────┴────────────────────────┐            │
│  │           API Client (SSE + REST)                │            │
│  └────────────────────────┬────────────────────────┘            │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                   Dashboard Lambda (FastAPI)                   │
├───────────────────────────────────────────────────────────────┤
│  GET /api/sentiment?tags=AI,climate&range=24h                  │
│  GET /api/articles?tags=AI&limit=20&sentiment=negative         │
│  GET /api/trends?tags=AI,climate&interval=1h                   │
│  POST /api/backfill {tags: [...], start: ..., end: ...}       │
│  GET /api/stream (SSE for real-time updates)                   │
└───────────────────────────┬───────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                      DynamoDB                                  │
├───────────────────────────────────────────────────────────────┤
│  sentiment_items table                                         │
│  - PK: source_id                                               │
│  - SK: ingested_at                                             │
│  - GSI: by_timestamp (for range queries)                       │
│  - GSI: by_tag (for per-topic queries)                         │
└───────────────────────────────────────────────────────────────┘
```

### Technology Stack

**Frontend:**
- React Native (Expo) for true native feel, OR
- Next.js PWA for web-first with native-like experience
- Framer Motion for animations
- D3.js or Victory Native for charts
- Zustand for state management
- Web Audio API for ambient sounds

**Backend:**
- Existing Dashboard Lambda (FastAPI) - extend with new endpoints
- SSE for real-time updates (already implemented)
- DynamoDB queries with new GSI for tag-based filtering

**Design:**
- Tailwind CSS with custom design tokens
- Radix UI primitives for accessibility
- Custom Mood Ring component (SVG + Canvas)

### New API Endpoints

```python
# Aggregate sentiment for topics
GET /api/v2/sentiment
  ?tags=AI,climate,economy
  &start=2025-11-24T00:00:00Z
  &end=2025-11-25T00:00:00Z

Response:
{
  "tags": {
    "AI": {"positive": 0.72, "neutral": 0.18, "negative": 0.10, "count": 145},
    "climate": {"positive": 0.45, "neutral": 0.30, "negative": 0.25, "count": 89}
  },
  "overall": {"positive": 0.58, "neutral": 0.24, "negative": 0.18},
  "trend": "improving"  // based on comparison to previous period
}

# Trend data for sparklines
GET /api/v2/trends
  ?tags=AI,climate
  &interval=1h  // 1h, 6h, 1d
  &range=7d

Response:
{
  "AI": [
    {"timestamp": "2025-11-24T00:00:00Z", "sentiment": 0.65, "count": 12},
    {"timestamp": "2025-11-24T01:00:00Z", "sentiment": 0.70, "count": 8},
    ...
  ]
}

# Historical backfill trigger
POST /api/v2/backfill
{
  "tags": ["AI", "climate"],
  "start": "2025-11-01T00:00:00Z",
  "end": "2025-11-24T00:00:00Z"
}

Response:
{
  "job_id": "backfill-abc123",
  "status": "started",
  "estimated_articles": 500
}

GET /api/v2/backfill/backfill-abc123
{
  "status": "in_progress",
  "progress": {"fetched": 250, "total": 500},
  "eta_seconds": 120
}
```

### DynamoDB Schema Updates

```
New GSI: by_tag_timestamp
- PK: tag (string) - e.g., "AI"
- SK: ingested_at (string) - ISO8601
- Projection: ALL

This enables efficient queries like:
"Get all AI articles from the past 24 hours sorted by time"
```

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: Dashboard loads in < 2 seconds on 4G (Lighthouse performance > 90)
- **SC-002**: 60fps animations verified on iPhone 12 and Pixel 6
- **SC-003**: User can complete tag selection flow in < 30 seconds
- **SC-004**: Mood Ring sentiment matches DynamoDB aggregate within 5%
- **SC-005**: Historical backfill completes within 5 minutes for 30-day range
- **SC-006**: SSE updates appear within 3 seconds of DynamoDB write
- **SC-007**: Offline mode serves cached data within 500ms

### Demo Day Checklist

1. [ ] User opens dashboard on phone → Beautiful loading animation
2. [ ] User adds 5 tags with haptic feedback
3. [ ] Mood Ring animates to show current sentiment
4. [ ] User selects "Past Week" → Data populates with progress
5. [ ] Real-time pulse shows data freshness
6. [ ] User swipes through tag comparisons
7. [ ] Article cards show with sentiment badges
8. [ ] User enables ambient audio → Mood-appropriate sounds play
9. [ ] User pulls to refresh → Satisfying animation
10. [ ] User shares comparison chart → Generates image

---

## Open Questions

1. **Framework Choice**: React Native (Expo) for native feel, or Next.js PWA for web-first?
2. **Audio Library**: Web Audio API directly, or Howler.js for better browser support?
3. **Chart Library**: Victory Native (React Native), or D3.js (web)?
4. **Backfill Strategy**: Synchronous (wait) or async (job queue with polling)?
5. **Offline Storage**: IndexedDB directly, or library like Dexie.js?

---

## Future Enhancements

- **Push Notifications**: Alert when sentiment shifts significantly
- **Widgets**: iOS/Android home screen widgets showing Mood Ring
- **Apple Watch**: Glanceable sentiment on wrist
- **Voice Control**: "Hey Siri, what's the sentiment on AI today?"
- **AR Mode**: Visualize sentiment in augmented reality (experimental)
- **Social Features**: Share sentiment reports, compare with friends
- **Prediction**: ML model predicting sentiment direction
