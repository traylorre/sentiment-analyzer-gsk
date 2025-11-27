# API Client Contract: Frontend to Backend

**Feature**: 007-sentiment-dashboard-frontend
**Date**: 2025-11-27
**Backend**: Feature 006 API (v2)

## Overview

This document defines the API client contract for the frontend. The client wraps Feature 006's REST API endpoints with TypeScript types and error handling.

---

## Base Configuration

```typescript
// src/lib/api/client.ts

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.example.com';

interface ApiClientConfig {
  baseUrl: string;
  getAuthToken: () => string | null;
  getAnonymousId: () => string | null;
  onUnauthorized: () => void;
  onRateLimited: (retryAfter: number) => void;
}

class ApiClient {
  private config: ApiClientConfig;

  constructor(config: ApiClientConfig) {
    this.config = config;
  }

  private async request<T>(
    method: string,
    path: string,
    options?: {
      body?: unknown;
      params?: Record<string, string>;
    }
  ): Promise<T> {
    const url = new URL(path, this.config.baseUrl);
    if (options?.params) {
      Object.entries(options.params).forEach(([key, value]) => {
        url.searchParams.set(key, value);
      });
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    const token = this.config.getAuthToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    } else {
      const anonymousId = this.config.getAnonymousId();
      if (anonymousId) {
        headers['X-Anonymous-ID'] = anonymousId;
      }
    }

    const response = await fetch(url.toString(), {
      method,
      headers,
      body: options?.body ? JSON.stringify(options.body) : undefined,
    });

    if (response.status === 401) {
      this.config.onUnauthorized();
      throw new ApiError('UNAUTHORIZED', 'Session expired');
    }

    if (response.status === 429) {
      const retryAfter = parseInt(response.headers.get('Retry-After') || '60');
      this.config.onRateLimited(retryAfter);
      throw new ApiError('RATE_LIMITED', `Rate limited. Retry after ${retryAfter}s`);
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(error.error?.code || 'UNKNOWN', error.error?.message || 'Request failed');
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  get<T>(path: string, params?: Record<string, string>): Promise<T> {
    return this.request<T>('GET', path, { params });
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>('POST', path, { body });
  }

  patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>('PATCH', path, { body });
  }

  delete<T>(path: string): Promise<T> {
    return this.request<T>('DELETE', path);
  }
}

class ApiError extends Error {
  constructor(public code: string, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export { ApiClient, ApiError };
```

---

## Authentication API

```typescript
// src/lib/api/auth.ts

import { ApiClient } from './client';
import type {
  AnonymousSession,
  AuthTokens,
  User
} from '@/types/auth';

interface AuthApi {
  // Anonymous
  createAnonymousSession(timezone: string): Promise<AnonymousSession>;
  validateAnonymousSession(userId: string): Promise<{ valid: boolean; expiresAt?: string }>;

  // Magic Link
  requestMagicLink(email: string, anonymousUserId?: string): Promise<{ status: string; expiresInSeconds: number }>;
  verifyMagicLink(token: string, sig: string): Promise<{
    status: string;
    userId: string;
    email: string;
    tokens: AuthTokens;
    mergedAnonymousData: boolean;
  }>;

  // OAuth
  getOAuthUrls(): Promise<{
    providers: {
      google: { authorizeUrl: string };
      github: { authorizeUrl: string };
    };
  }>;
  handleOAuthCallback(code: string, provider: string, anonymousUserId?: string): Promise<{
    status: string;
    userId: string;
    email: string;
    tokens: AuthTokens;
    mergedAnonymousData: boolean;
    isNewUser: boolean;
  }>;

  // Session
  refreshTokens(refreshToken: string): Promise<{ idToken: string; accessToken: string; expiresIn: number }>;
  signOut(): Promise<void>;
  getSession(): Promise<{
    userId: string;
    email: string;
    authType: string;
    sessionExpiresAt: string;
    linkedProviders: string[];
  }>;
  extendSession(): Promise<{ sessionExpiresAt: string }>;

  // User
  getCurrentUser(): Promise<User>;
  updateUserPreferences(preferences: { timezone?: string; emailNotificationsEnabled?: boolean }): Promise<User>;
}

export function createAuthApi(client: ApiClient): AuthApi {
  return {
    // Anonymous
    createAnonymousSession: (timezone) =>
      client.post('/api/v2/auth/anonymous', { timezone }),

    validateAnonymousSession: (userId) =>
      client.get('/api/v2/auth/validate', { userId }),

    // Magic Link
    requestMagicLink: (email, anonymousUserId) =>
      client.post('/api/v2/auth/magic-link', { email, anonymous_user_id: anonymousUserId }),

    verifyMagicLink: (token, sig) =>
      client.get(`/api/v2/auth/magic-link/verify`, { token, sig }),

    // OAuth
    getOAuthUrls: () =>
      client.get('/api/v2/auth/oauth/urls'),

    handleOAuthCallback: (code, provider, anonymousUserId) =>
      client.post('/api/v2/auth/oauth/callback', {
        code,
        provider,
        anonymous_user_id: anonymousUserId,
      }),

    // Session
    refreshTokens: (refreshToken) =>
      client.post('/api/v2/auth/refresh', { refresh_token: refreshToken }),

    signOut: () =>
      client.post('/api/v2/auth/signout'),

    getSession: () =>
      client.get('/api/v2/auth/session'),

    extendSession: () =>
      client.post('/api/v2/auth/extend'),

    // User
    getCurrentUser: () =>
      client.get('/api/v2/users/me'),

    updateUserPreferences: (preferences) =>
      client.patch('/api/v2/users/me', preferences),
  };
}
```

---

## Configuration API

```typescript
// src/lib/api/configs.ts

import { ApiClient } from './client';
import type {
  Configuration,
  ConfigurationList,
  CreateConfigRequest,
  UpdateConfigRequest
} from '@/types/config';

interface ConfigsApi {
  list(): Promise<ConfigurationList>;
  get(configId: string): Promise<Configuration>;
  create(config: CreateConfigRequest): Promise<Configuration>;
  update(configId: string, updates: UpdateConfigRequest): Promise<Configuration>;
  delete(configId: string): Promise<void>;
}

export function createConfigsApi(client: ApiClient): ConfigsApi {
  return {
    list: () =>
      client.get('/api/v2/configurations'),

    get: (configId) =>
      client.get(`/api/v2/configurations/${configId}`),

    create: (config) =>
      client.post('/api/v2/configurations', {
        name: config.name,
        tickers: config.tickers,
        timeframe_days: config.timeframeDays,
        include_extended_hours: config.includeExtendedHours,
      }),

    update: (configId, updates) =>
      client.patch(`/api/v2/configurations/${configId}`, {
        name: updates.name,
        tickers: updates.tickers,
        timeframe_days: updates.timeframeDays,
        include_extended_hours: updates.includeExtendedHours,
      }),

    delete: (configId) =>
      client.delete(`/api/v2/configurations/${configId}`),
  };
}
```

---

## Sentiment API

```typescript
// src/lib/api/sentiment.ts

import { ApiClient } from './client';
import type {
  SentimentData,
  HeatMapData
} from '@/types/sentiment';

interface SentimentApi {
  getByConfig(configId: string, sources?: string[]): Promise<SentimentData>;
  getHeatMap(configId: string, view: 'sources' | 'timeperiods'): Promise<HeatMapData>;
  getTimeSeries(configId: string, ticker: string, source: string): Promise<{
    data: Array<{ timestamp: string; score: number }>;
  }>;
  refresh(configId: string): Promise<{ status: string; estimatedCompletion: string }>;
  getRefreshStatus(configId: string): Promise<{
    lastRefresh: string;
    nextScheduledRefresh: string;
    refreshIntervalSeconds: number;
    countdownSeconds: number;
    isRefreshing: boolean;
  }>;
}

export function createSentimentApi(client: ApiClient): SentimentApi {
  return {
    getByConfig: (configId, sources) =>
      client.get(`/api/v2/configurations/${configId}/sentiment`, {
        sources: sources?.join(','),
      }),

    getHeatMap: (configId, view) =>
      client.get(`/api/v2/configurations/${configId}/heatmap`, { view }),

    getTimeSeries: (configId, ticker, source) =>
      client.get(`/api/v2/configurations/${configId}/sentiment/timeseries`, {
        ticker,
        source,
      }),

    refresh: (configId) =>
      client.post(`/api/v2/configurations/${configId}/refresh`),

    getRefreshStatus: (configId) =>
      client.get(`/api/v2/configurations/${configId}/refresh/status`),
  };
}
```

---

## Volatility API

```typescript
// src/lib/api/volatility.ts

import { ApiClient } from './client';
import type { TickerVolatility } from '@/types/volatility';

interface VolatilityApi {
  getByConfig(configId: string): Promise<{
    configId: string;
    tickers: TickerVolatility[];
  }>;
  getCorrelation(configId: string): Promise<{
    configId: string;
    tickers: Array<{
      symbol: string;
      correlation: {
        sentimentTrend: string;
        volatilityTrend: string;
        interpretation: string;
        description: string;
      };
    }>;
  }>;
}

export function createVolatilityApi(client: ApiClient): VolatilityApi {
  return {
    getByConfig: (configId) =>
      client.get(`/api/v2/configurations/${configId}/volatility`),

    getCorrelation: (configId) =>
      client.get(`/api/v2/configurations/${configId}/correlation`),
  };
}
```

---

## Alerts API

```typescript
// src/lib/api/alerts.ts

import { ApiClient } from './client';
import type {
  AlertRule,
  AlertList,
  CreateAlertRequest,
  Notification
} from '@/types/alert';

interface AlertsApi {
  list(filters?: { configId?: string; ticker?: string; enabled?: boolean }): Promise<AlertList>;
  get(alertId: string): Promise<AlertRule>;
  create(alert: CreateAlertRequest): Promise<AlertRule>;
  update(alertId: string, updates: { thresholdValue?: number; isEnabled?: boolean }): Promise<AlertRule>;
  delete(alertId: string): Promise<void>;
  toggle(alertId: string): Promise<{ alertId: string; isEnabled: boolean }>;

  // Notifications
  getNotifications(filters?: {
    status?: string;
    alertId?: string;
    limit?: number;
    offset?: number
  }): Promise<{
    notifications: Notification[];
    total: number;
  }>;
  getNotification(notificationId: string): Promise<Notification>;
}

export function createAlertsApi(client: ApiClient): AlertsApi {
  return {
    list: (filters) =>
      client.get('/api/v2/alerts', filters as Record<string, string>),

    get: (alertId) =>
      client.get(`/api/v2/alerts/${alertId}`),

    create: (alert) =>
      client.post('/api/v2/alerts', {
        config_id: alert.configId,
        ticker: alert.ticker,
        alert_type: alert.alertType,
        threshold_value: alert.thresholdValue,
        threshold_direction: alert.thresholdDirection,
      }),

    update: (alertId, updates) =>
      client.patch(`/api/v2/alerts/${alertId}`, {
        threshold_value: updates.thresholdValue,
        is_enabled: updates.isEnabled,
      }),

    delete: (alertId) =>
      client.delete(`/api/v2/alerts/${alertId}`),

    toggle: (alertId) =>
      client.post(`/api/v2/alerts/${alertId}/toggle`),

    getNotifications: (filters) =>
      client.get('/api/v2/notifications', filters as Record<string, string>),

    getNotification: (notificationId) =>
      client.get(`/api/v2/notifications/${notificationId}`),
  };
}
```

---

## Ticker Validation API

```typescript
// src/lib/api/tickers.ts

import { ApiClient } from './client';

interface TickerValidation {
  symbol: string;
  status: 'valid' | 'delisted' | 'invalid';
  name?: string;
  exchange?: string;
  successor?: string;
  message?: string;
}

interface TickerSearchResult {
  symbol: string;
  name: string;
  exchange: string;
}

interface TickersApi {
  validate(symbol: string): Promise<TickerValidation>;
  search(query: string, limit?: number): Promise<{ results: TickerSearchResult[] }>;
}

export function createTickersApi(client: ApiClient): TickersApi {
  return {
    validate: (symbol) =>
      client.get('/api/v2/tickers/validate', { symbol }),

    search: (query, limit = 10) =>
      client.get('/api/v2/tickers/search', { q: query, limit: String(limit) }),
  };
}
```

---

## Market Status API

```typescript
// src/lib/api/market.ts

import { ApiClient } from './client';

interface MarketStatus {
  status: 'open' | 'closed';
  exchange: string;
  currentTime: string;
  marketOpen: string | null;
  marketClose: string | null;
  nextOpen: string | null;
  reason?: string;
  isHoliday?: boolean;
  holidayName?: string;
  isExtendedHours: boolean;
}

interface PremarketEstimate {
  symbol: string;
  premarketPrice: number;
  previousClose: number;
  changePercent: number;
  estimatedSentiment: {
    score: number;
    label: string;
    confidence: number;
    basis: string;
  };
  overnightNewsCount: number;
  updatedAt: string;
}

interface MarketApi {
  getStatus(): Promise<MarketStatus>;
  getPremarketEstimates(configId: string): Promise<{
    configId: string;
    marketStatus: string;
    dataSource: string;
    estimates: PremarketEstimate[];
    disclaimer: string;
    nextMarketOpen: string;
  }>;
}

export function createMarketApi(client: ApiClient): MarketApi {
  return {
    getStatus: () =>
      client.get('/api/v2/market/status'),

    getPremarketEstimates: (configId) =>
      client.get(`/api/v2/configurations/${configId}/premarket`),
  };
}
```

---

## SSE Client

```typescript
// src/lib/api/sse.ts

export interface SSEConfig {
  configId: string;
  baseUrl: string;
  token?: string;
  onSentimentUpdate: (data: SentimentData) => void;
  onConnectionChange: (status: 'connected' | 'reconnecting' | 'error') => void;
  onError: (error: Error) => void;
}

export function createSSEConnection(config: SSEConfig): {
  connect: () => void;
  disconnect: () => void;
} {
  let eventSource: EventSource | null = null;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;
  const baseReconnectDelay = 1000;

  const connect = () => {
    const url = new URL(
      `/api/v2/configurations/${config.configId}/stream`,
      config.baseUrl
    );
    if (config.token) {
      url.searchParams.set('token', config.token);
    }

    eventSource = new EventSource(url.toString());

    eventSource.onopen = () => {
      reconnectAttempts = 0;
      config.onConnectionChange('connected');
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        config.onSentimentUpdate(data);
      } catch (error) {
        config.onError(new Error('Failed to parse SSE message'));
      }
    };

    eventSource.onerror = () => {
      config.onConnectionChange('reconnecting');
      eventSource?.close();

      if (reconnectAttempts < maxReconnectAttempts) {
        const delay = baseReconnectDelay * Math.pow(2, reconnectAttempts);
        reconnectAttempts++;
        setTimeout(connect, delay);
      } else {
        config.onConnectionChange('error');
        config.onError(new Error('Max reconnection attempts reached'));
      }
    };
  };

  const disconnect = () => {
    eventSource?.close();
    eventSource = null;
  };

  return { connect, disconnect };
}
```

---

## React Query Hooks

```typescript
// src/hooks/use-configs.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

export function useConfigurations() {
  return useQuery({
    queryKey: ['configurations'],
    queryFn: () => api.configs.list(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useSentiment(configId: string) {
  return useQuery({
    queryKey: ['sentiment', configId],
    queryFn: () => api.sentiment.getByConfig(configId),
    staleTime: 60 * 1000, // 1 minute (SSE will update)
    enabled: !!configId,
  });
}

export function useCreateConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: api.configs.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['configurations'] });
    },
  });
}

export function useDeleteConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: api.configs.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['configurations'] });
    },
  });
}
```

---

## Error Codes Reference

| Code | HTTP | Meaning | UI Action |
|------|------|---------|-----------|
| `VALIDATION_ERROR` | 400 | Invalid input | Show field errors |
| `INVALID_TICKER` | 400 | Ticker not found | Show inline error + suggestions |
| `UNAUTHORIZED` | 401 | Session expired | Show auth modal |
| `FORBIDDEN` | 403 | Not allowed | Show upgrade prompt |
| `NOT_FOUND` | 404 | Resource missing | Navigate to dashboard |
| `CONFLICT` | 409 | Max configs reached | Show limit message |
| `RATE_LIMITED` | 429 | Too many requests | Show "Taking a breather" |
| `SERVICE_UNAVAILABLE` | 503 | API down | Show "We'll be back" |
| `UPSTREAM_ERROR` | 502 | Tiingo/Finnhub error | Show cached data + warning |
