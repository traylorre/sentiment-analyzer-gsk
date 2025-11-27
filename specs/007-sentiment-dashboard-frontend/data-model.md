# Data Model: Sentiment Dashboard Frontend

**Feature**: 007-sentiment-dashboard-frontend
**Date**: 2025-11-27

## Overview

This document defines the frontend state models and TypeScript types. The frontend consumes Feature 006 backend APIs and maintains local state for UI interactions, gestures, and animations.

---

## Core Domain Types

### Sentiment Types

```typescript
// src/types/sentiment.ts

export type SentimentLabel = 'positive' | 'neutral' | 'negative';

export interface SentimentScore {
  score: number;              // -1.0 to 1.0
  label: SentimentLabel;
  confidence: number;         // 0.0 to 1.0
  updatedAt: string;          // ISO 8601
}

export interface TickerSentiment {
  symbol: string;
  sentiment: {
    tiingo: SentimentScore;
    finnhub: SentimentScore;
    ourModel: SentimentScore;
  };
}

export interface SentimentData {
  configId: string;
  tickers: TickerSentiment[];
  lastUpdated: string;
  nextRefreshAt: string;
  cacheStatus: 'fresh' | 'stale' | 'error';
}

export interface SentimentTimeSeries {
  timestamp: string;
  score: number;
  source: 'tiingo' | 'finnhub' | 'our_model';
}
```

### Volatility Types

```typescript
// src/types/volatility.ts

export type TrendDirection = 'increasing' | 'decreasing' | 'stable';

export interface ATRData {
  value: number;              // Absolute ATR value
  percent: number;            // ATR as percentage of price
  period: number;             // Days (typically 14)
  trend: TrendDirection;
  trendArrow: '↑' | '↓' | '→';
  previousValue: number;
}

export interface TickerVolatility {
  symbol: string;
  atr: ATRData;
  includesExtendedHours: boolean;
  updatedAt: string;
}
```

### Configuration Types

```typescript
// src/types/config.ts

export interface TickerConfig {
  symbol: string;
  name: string;
  exchange: 'NYSE' | 'NASDAQ' | 'AMEX';
}

export interface Configuration {
  configId: string;
  name: string;
  tickers: TickerConfig[];
  timeframeDays: number;
  includeExtendedHours: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ConfigurationList {
  configurations: Configuration[];
  maxAllowed: number;
}

export interface CreateConfigRequest {
  name: string;
  tickers: string[];          // Just symbols, backend validates
  timeframeDays: number;
  includeExtendedHours: boolean;
}

export interface UpdateConfigRequest {
  name?: string;
  tickers?: string[];
  timeframeDays?: number;
  includeExtendedHours?: boolean;
}
```

### Authentication Types

```typescript
// src/types/auth.ts

export type AuthType = 'anonymous' | 'email' | 'google' | 'github';

export interface User {
  userId: string;
  authType: AuthType;
  email?: string;
  createdAt: string;
  configurationCount: number;
  alertCount: number;
  emailNotificationsEnabled: boolean;
}

export interface AuthTokens {
  idToken: string;
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

export interface AnonymousSession {
  userId: string;
  authType: 'anonymous';
  createdAt: string;
  sessionExpiresAt: string;
  storageHint: 'localStorage';
}

export interface AuthState {
  isAuthenticated: boolean;
  isAnonymous: boolean;
  user: User | null;
  tokens: AuthTokens | null;
  sessionExpiresAt: string | null;
}
```

### Alert Types

```typescript
// src/types/alert.ts

export type AlertType = 'sentiment_threshold' | 'volatility_threshold';
export type ThresholdDirection = 'above' | 'below';

export interface AlertRule {
  alertId: string;
  configId: string;
  ticker: string;
  alertType: AlertType;
  thresholdValue: number;
  thresholdDirection: ThresholdDirection;
  isEnabled: boolean;
  lastTriggeredAt: string | null;
  triggerCount: number;
  createdAt: string;
}

export interface AlertList {
  alerts: AlertRule[];
  total: number;
  dailyEmailQuota: {
    used: number;
    limit: number;
    resetsAt: string;
  };
}

export interface CreateAlertRequest {
  configId: string;
  ticker: string;
  alertType: AlertType;
  thresholdValue: number;
  thresholdDirection: ThresholdDirection;
}

export interface Notification {
  notificationId: string;
  alertId: string;
  ticker: string;
  alertType: AlertType;
  triggeredValue: number;
  thresholdValue: number;
  subject: string;
  sentAt: string;
  status: 'sent' | 'failed' | 'pending';
  deepLink: string;
}
```

---

## UI State Models

### View State (Zustand Store)

```typescript
// src/stores/view-store.ts

export type ViewName = 'dashboard' | 'configs' | 'alerts' | 'settings';

export interface ViewState {
  // Navigation
  currentView: ViewName;
  previousView: ViewName | null;
  viewHistory: ViewName[];

  // Gestures
  gestureProgress: number;        // 0.0 to 1.0 for swipe progress
  gestureDirection: 'left' | 'right' | null;
  isGestureActive: boolean;

  // Bottom Sheet
  isBottomSheetOpen: boolean;
  bottomSheetContent: 'quickActions' | 'tickerSearch' | 'alertCreate' | null;

  // Actions
  navigateTo: (view: ViewName) => void;
  setGestureProgress: (progress: number, direction: 'left' | 'right' | null) => void;
  completeGesture: () => void;
  cancelGesture: () => void;
  openBottomSheet: (content: ViewState['bottomSheetContent']) => void;
  closeBottomSheet: () => void;
}
```

### Animation State (Zustand Store)

```typescript
// src/stores/animation-store.ts

export type AnimationPriority = 'high' | 'medium' | 'low';

export interface PendingAnimation {
  id: string;
  type: 'entrance' | 'exit' | 'update' | 'celebration';
  target: string;               // Component identifier
  priority: AnimationPriority;
  duration: number;             // milliseconds
  delay: number;
}

export interface AnimationState {
  // Queue
  pendingAnimations: PendingAnimation[];
  activeAnimations: string[];   // Animation IDs currently running

  // Preferences
  reducedMotion: boolean;
  hapticEnabled: boolean;

  // Actions
  queueAnimation: (animation: Omit<PendingAnimation, 'id'>) => string;
  startAnimation: (id: string) => void;
  completeAnimation: (id: string) => void;
  cancelAnimation: (id: string) => void;
  setReducedMotion: (enabled: boolean) => void;
  setHapticEnabled: (enabled: boolean) => void;
}
```

### Chart State (Zustand Store)

```typescript
// src/stores/chart-store.ts

export interface ChartState {
  // Active chart
  activeConfigId: string | null;
  activeTicker: string | null;
  activeSource: 'tiingo' | 'finnhub' | 'our_model' | null;

  // Interaction
  isScrubbing: boolean;
  scrubPosition: number | null;   // X position as percentage (0-100)
  scrubValue: number | null;      // Sentiment value at scrub position
  scrubTimestamp: string | null;

  // Heat map
  heatMapView: 'sources' | 'timeperiods';
  hoveredCell: { ticker: string; source: string } | null;

  // Actions
  setActiveTicker: (ticker: string) => void;
  startScrub: (position: number) => void;
  updateScrub: (position: number, value: number, timestamp: string) => void;
  endScrub: () => void;
  setHeatMapView: (view: 'sources' | 'timeperiods') => void;
  setHoveredCell: (cell: ChartState['hoveredCell']) => void;
}
```

### Auth State (Zustand Store)

```typescript
// src/stores/auth-store.ts

export interface AuthStoreState {
  // State
  isInitialized: boolean;
  isAuthenticated: boolean;
  isAnonymous: boolean;
  user: User | null;
  tokens: AuthTokens | null;

  // Auth modal
  isAuthModalOpen: boolean;
  authModalStep: 'options' | 'magic-link' | 'checking-email' | 'success' | 'error';
  authError: string | null;

  // Actions
  initialize: () => Promise<void>;
  createAnonymousSession: () => Promise<void>;
  requestMagicLink: (email: string) => Promise<void>;
  verifyMagicLink: (token: string, sig: string) => Promise<void>;
  handleOAuthCallback: (code: string, provider: 'google' | 'github') => Promise<void>;
  refreshTokens: () => Promise<void>;
  signOut: () => Promise<void>;
  openAuthModal: () => void;
  closeAuthModal: () => void;
  setAuthModalStep: (step: AuthStoreState['authModalStep']) => void;
}
```

### Config State (Zustand Store)

```typescript
// src/stores/config-store.ts

export interface ConfigStoreState {
  // Data
  configurations: Configuration[];
  activeConfigId: string | null;
  maxConfigs: number;

  // Loading states
  isLoading: boolean;
  isSaving: boolean;
  isDeleting: boolean;

  // Edit state
  editingConfigId: string | null;
  pendingChanges: Partial<UpdateConfigRequest> | null;

  // Actions
  fetchConfigurations: () => Promise<void>;
  setActiveConfig: (configId: string) => void;
  createConfiguration: (config: CreateConfigRequest) => Promise<Configuration>;
  updateConfiguration: (configId: string, updates: UpdateConfigRequest) => Promise<void>;
  deleteConfiguration: (configId: string) => Promise<void>;
  startEditing: (configId: string) => void;
  cancelEditing: () => void;
  setPendingChanges: (changes: Partial<UpdateConfigRequest>) => void;
}
```

---

## Heat Map Data Model

```typescript
// src/types/heatmap.ts

export interface HeatMapCell {
  source: 'tiingo' | 'finnhub' | 'our_model';  // For sources view
  period: 'today' | '1w' | '1m' | '3m';        // For timeperiods view
  score: number;
  color: string;                                // Computed hex color
}

export interface HeatMapRow {
  ticker: string;
  cells: HeatMapCell[];
}

export interface HeatMapData {
  view: 'sources' | 'timeperiods';
  matrix: HeatMapRow[];
  legend: {
    positive: { range: [number, number]; color: string };
    neutral: { range: [number, number]; color: string };
    negative: { range: [number, number]; color: string };
  };
}
```

---

## Refresh & Connection State

```typescript
// src/types/connection.ts

export type ConnectionStatus = 'connected' | 'reconnecting' | 'offline' | 'error';

export interface RefreshState {
  lastRefresh: string;
  nextScheduledRefresh: string;
  refreshIntervalSeconds: number;
  countdownSeconds: number;
  isRefreshing: boolean;
}

export interface ConnectionState {
  status: ConnectionStatus;
  lastConnectedAt: string | null;
  reconnectAttempts: number;
  error: string | null;
}
```

---

## Color Mapping Utility

```typescript
// src/lib/utils/colors.ts

export const SENTIMENT_COLORS = {
  positive: '#22C55E',  // Green
  neutral: '#EAB308',   // Yellow
  negative: '#EF4444',  // Red
  accent: '#00FFFF',    // Cyan
} as const;

export function getSentimentColor(score: number): string {
  if (score >= 0.33) return SENTIMENT_COLORS.positive;
  if (score <= -0.33) return SENTIMENT_COLORS.negative;
  return SENTIMENT_COLORS.neutral;
}

export function getSentimentGradient(score: number): string {
  // Returns CSS gradient for chart fills
  const color = getSentimentColor(score);
  return `linear-gradient(180deg, ${color}40 0%, ${color}00 100%)`;
}

export function getScoreLabel(score: number): SentimentLabel {
  if (score >= 0.33) return 'positive';
  if (score <= -0.33) return 'negative';
  return 'neutral';
}
```

---

## Local Storage Schema

```typescript
// Frontend localStorage keys and shapes

interface LocalStorageSchema {
  // Anonymous session
  'sentiment_user_id': string;
  'sentiment_auth_type': AuthType;
  'sentiment_session_expires': string;

  // Authenticated session
  'sentiment_tokens': AuthTokens;

  // UI preferences
  'sentiment_haptic_enabled': boolean;
  'sentiment_reduced_motion': boolean;

  // Cache (with timestamps)
  'sentiment_config_cache': {
    data: Configuration[];
    timestamp: string;
  };
}
```
