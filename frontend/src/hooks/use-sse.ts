'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  SSEClient,
  SSEStatus,
  SSEMessage,
  SentimentUpdatePayload,
} from '@/lib/api/sse';

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

    const baseUrl = process.env.NEXT_PUBLIC_API_URL || '';

    // Build URL based on whether this is a config-specific or global stream
    let url: string;
    if (configId) {
      // Config-specific stream requires authentication via user_token query param
      // Note: EventSource API does not support custom headers, so token must be in URL
      url = `${baseUrl}/api/v2/configurations/${configId}/stream`;
      if (userToken) {
        url += `?user_token=${encodeURIComponent(userToken)}`;
      }
    } else {
      // Global stream (no authentication required)
      url = `${baseUrl}/api/v2/stream`;
    }

    clientRef.current = new SSEClient(url, {
      onMessage: handleMessage,
      onStatusChange: handleStatusChange,
      onError: handleError,
    });

    clientRef.current.connect();
  }, [configId, userToken, handleMessage, handleStatusChange, handleError]);

  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
      clientRef.current = null;
    }
  }, []);

  // Auto-connect when enabled
  useEffect(() => {
    if (enabled) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, connect, disconnect]);

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
