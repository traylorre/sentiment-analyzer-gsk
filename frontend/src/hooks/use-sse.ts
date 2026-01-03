'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  SSEClient,
  SSEStatus,
  SSEMessage,
  SentimentUpdatePayload,
} from '@/lib/api/sse';
import { joinUrl } from '@/lib/utils/url';
import { useRuntimeStore, useRuntimeLoaded } from '@/stores/runtime-store';

interface UseSSEOptions {
  configId?: string;
  /**
   * User token for authenticated config-specific streams.
   * Required when configId is provided.
   *
   * Note: EventSource API does not support custom HTTP headers,
   * so the token must be passed as a query parameter. Use short-lived
   * tokens for security (tokens in URLs appear in browser history and logs).
   */
  userToken?: string;
  enabled?: boolean;
  onUpdate?: (payload: SentimentUpdatePayload) => void;
}

interface UseSSEResult {
  status: SSEStatus;
  isConnected: boolean;
  lastUpdate: string | null;
  connect: () => void;
  disconnect: () => void;
}

export function useSSE(options: UseSSEOptions = {}): UseSSEResult {
  const { configId, userToken, enabled = true, onUpdate } = options;

  const [status, setStatus] = useState<SSEStatus>('disconnected');
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const clientRef = useRef<SSEClient | null>(null);
  const queryClient = useQueryClient();

  // Feature 1100: Get SSE URL from runtime config
  const getSseBaseUrl = useRuntimeStore((state) => state.getSseBaseUrl);
  const runtimeLoaded = useRuntimeLoaded();

  const handleMessage = useCallback(
    (message: SSEMessage) => {
      if (message.type === 'sentiment_update') {
        const payload = message.data as SentimentUpdatePayload;

        // Filter by configId if provided
        if (configId && payload.configId !== configId) {
          return;
        }

        setLastUpdate(message.timestamp);

        // Invalidate relevant queries to trigger re-fetch
        queryClient.invalidateQueries({ queryKey: ['sentiment'] });
        queryClient.invalidateQueries({ queryKey: ['metrics'] });

        // Call the custom update handler
        onUpdate?.(payload);
      }
    },
    [configId, queryClient, onUpdate]
  );

  const handleStatusChange = useCallback((newStatus: SSEStatus) => {
    setStatus(newStatus);
  }, []);

  const handleError = useCallback((error: Error) => {
    console.error('SSE Error:', error.message);
  }, []);

  const connect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
    }

    // Feature 1100: Use SSE Lambda URL from runtime config
    // Falls back to NEXT_PUBLIC_API_URL if runtime config not available
    const baseUrl = getSseBaseUrl();

    // Build URL based on whether this is a config-specific or global stream
    // Gap 4: Use same-origin proxy when available (cookie auth, no token in URL)
    const useProxy = process.env.NEXT_PUBLIC_USE_SSE_PROXY === 'true';
    let url: string;

    if (configId) {
      if (useProxy) {
        // Same-origin proxy: cookie sent automatically, token never in URL
        // Security: HttpOnly cookie prevents XSS theft, no URL logging exposure
        url = `/api/sse/configurations/${configId}/stream`;
      } else {
        // Legacy: token in URL (preprod temporary mitigation with short expiry)
        // Feature 1118: Use joinUrl to prevent double-slash issues
        url = joinUrl(baseUrl, `/api/v2/configurations/${configId}/stream`);
        if (userToken) {
          url += `?user_token=${encodeURIComponent(userToken)}`;
        }
      }
    } else {
      // Global stream (no authentication required)
      // Feature 1118: Use joinUrl to prevent double-slash issues
      url = useProxy ? '/api/sse/stream' : joinUrl(baseUrl, '/api/v2/stream');
    }

    clientRef.current = new SSEClient(url, {
      onMessage: handleMessage,
      onStatusChange: handleStatusChange,
      onError: handleError,
    });

    clientRef.current.connect();
  }, [configId, userToken, getSseBaseUrl, handleMessage, handleStatusChange, handleError]);

  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
      clientRef.current = null;
    }
  }, []);

  // Auto-connect when enabled and runtime config is loaded
  // Feature 1100: Wait for runtime config to be loaded before connecting
  useEffect(() => {
    if (enabled && runtimeLoaded) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, runtimeLoaded, connect, disconnect]);

  // Reconnect when configId or userToken changes
  useEffect(() => {
    if (enabled && clientRef.current) {
      disconnect();
      connect();
    }
  }, [configId, userToken, enabled, connect, disconnect]);

  return {
    status,
    isConnected: status === 'connected',
    lastUpdate,
    connect,
    disconnect,
  };
}

// Hook for tracking which values have updated (for glow animation)
interface UpdateTracker {
  [key: string]: {
    updated: boolean;
    timestamp: number;
  };
}

const GLOW_DURATION_MS = 2000;

export function useUpdateTracker() {
  const [updates, setUpdates] = useState<UpdateTracker>({});

  const markUpdated = useCallback((key: string) => {
    setUpdates((prev) => ({
      ...prev,
      [key]: { updated: true, timestamp: Date.now() },
    }));

    // Clear the update flag after animation duration
    setTimeout(() => {
      setUpdates((prev) => ({
        ...prev,
        [key]: { ...prev[key], updated: false },
      }));
    }, GLOW_DURATION_MS);
  }, []);

  const isUpdated = useCallback(
    (key: string) => {
      return updates[key]?.updated ?? false;
    },
    [updates]
  );

  const clearAll = useCallback(() => {
    setUpdates({});
  }, []);

  return {
    markUpdated,
    isUpdated,
    clearAll,
  };
}
