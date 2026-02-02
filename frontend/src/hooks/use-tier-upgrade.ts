/**
 * Hook for polling tier upgrade status after payment.
 *
 * Feature: 1191 - Mid-Session Tier Upgrade
 *
 * Implements exponential backoff polling (1s, 2s, 4s, 8s, 16s, 29s = 60s total)
 * to detect when backend processes Stripe webhook.
 */

import { useCallback, useRef, useState } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { authApi } from '@/lib/api';
import { getAuthBroadcastSync } from '@/lib/sync/broadcast-channel';
import { toast } from 'sonner';
import { ApiClientError } from '@/lib/api/client';

// Exponential backoff intervals (total: 60s)
const BACKOFF_INTERVALS = [1000, 2000, 4000, 8000, 16000, 29000];

export interface TierUpgradeState {
  isPolling: boolean;
  attemptCount: number;
  success: boolean;
  timedOut: boolean;
  error: string | null;
}

export interface UseTierUpgradeReturn {
  state: TierUpgradeState;
  startPolling: () => Promise<boolean>;
  stopPolling: () => void;
  retry: () => Promise<boolean>;
}

/**
 * Hook for detecting tier upgrade after payment.
 *
 * Usage:
 * ```tsx
 * const { state, startPolling, retry } = useTierUpgrade();
 *
 * // After payment callback
 * const handlePaymentSuccess = async () => {
 *   const upgraded = await startPolling();
 *   if (upgraded) {
 *     router.push('/dashboard');
 *   }
 * };
 * ```
 */
export function useTierUpgrade(): UseTierUpgradeReturn {
  const [state, setState] = useState<TierUpgradeState>({
    isPolling: false,
    attemptCount: 0,
    success: false,
    timedOut: false,
    error: null,
  });

  const abortRef = useRef(false);
  const setUser = useAuthStore((s) => s.setUser);

  const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

  const pollForUpgrade = useCallback(async (): Promise<boolean> => {
    abortRef.current = false;

    setState({
      isPolling: true,
      attemptCount: 0,
      success: false,
      timedOut: false,
      error: null,
    });

    for (let i = 0; i < BACKOFF_INTERVALS.length; i++) {
      if (abortRef.current) {
        setState((s) => ({ ...s, isPolling: false }));
        return false;
      }

      const delay = BACKOFF_INTERVALS[i];
      await sleep(delay);

      setState((s) => ({ ...s, attemptCount: i + 1 }));

      try {
        // Refresh user profile to get updated role
        const profile = await authApi.getProfile();

        // Check if role is now 'paid'
        if (profile.role === 'paid') {
          // Update local state
          const currentUser = useAuthStore.getState().user;
          if (currentUser) {
            setUser({
              ...currentUser,
              role: profile.role,
              subscriptionActive: profile.subscriptionActive,
              subscriptionExpiresAt: profile.subscriptionExpiresAt,
              roleAssignedAt: profile.roleAssignedAt,
            });
          }

          // Broadcast to other tabs
          const broadcastSync = getAuthBroadcastSync();
          broadcastSync.broadcast('ROLE_UPGRADED', {
            userId: currentUser?.userId,
            newRole: 'paid',
          });

          // Show success toast
          toast.success('Upgrade successful! Premium features unlocked.', {
            duration: 5000,
          });

          setState({
            isPolling: false,
            attemptCount: i + 1,
            success: true,
            timedOut: false,
            error: null,
          });

          return true;
        }
      } catch (error) {
        // Distinguish permanent vs transient errors
        if (error instanceof ApiClientError) {
          // 4xx errors are permanent - stop polling
          if (error.status >= 400 && error.status < 500) {
            console.error('[useTierUpgrade] Permanent error, stopping poll:', error.code, error.message);
            setState({
              isPolling: false,
              attemptCount: i + 1,
              success: false,
              timedOut: false,
              error: error.message,
            });
            toast.error(`Upgrade check failed: ${error.message}`);
            return false;
          }
        }
        // 5xx, network errors, timeouts - continue polling (transient)
        console.warn('[useTierUpgrade] Transient error, continuing poll:', error);
      }
    }

    // Timeout - webhook may be delayed
    toast.info(
      'Payment processing is taking longer than expected. Please refresh the page in a moment.',
      {
        duration: 10000,
        action: {
          label: 'Refresh',
          onClick: () => window.location.reload(),
        },
      }
    );

    setState({
      isPolling: false,
      attemptCount: BACKOFF_INTERVALS.length,
      success: false,
      timedOut: true,
      error: null,
    });

    return false;
  }, [setUser]);

  const stopPolling = useCallback(() => {
    abortRef.current = true;
  }, []);

  const retry = useCallback(async (): Promise<boolean> => {
    setState({
      isPolling: false,
      attemptCount: 0,
      success: false,
      timedOut: false,
      error: null,
    });
    return pollForUpgrade();
  }, [pollForUpgrade]);

  return {
    state,
    startPolling: pollForUpgrade,
    stopPolling,
    retry,
  };
}
