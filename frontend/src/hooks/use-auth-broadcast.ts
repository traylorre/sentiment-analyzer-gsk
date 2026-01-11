/**
 * Hook to initialize BroadcastChannel for cross-tab auth synchronization.
 *
 * Feature: 1191 - Mid-Session Tier Upgrade
 *
 * Use this hook in the root layout or auth provider to enable
 * cross-tab synchronization of auth state changes.
 */

import { useEffect } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { getAuthBroadcastSync } from '@/lib/sync/broadcast-channel';
import { authApi } from '@/lib/api';

/**
 * Initialize cross-tab auth synchronization.
 *
 * When another tab broadcasts ROLE_UPGRADED, this tab will
 * refresh the user profile to get the updated role.
 *
 * Usage:
 * ```tsx
 * // In root layout or auth provider
 * function AuthProvider({ children }) {
 *   useAuthBroadcast();
 *   return <>{children}</>;
 * }
 * ```
 */
export function useAuthBroadcast(): void {
  const setUser = useAuthStore((s) => s.setUser);
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    const broadcastSync = getAuthBroadcastSync();
    broadcastSync.connect();

    // Handle role upgrade from other tabs
    const handleRoleUpgraded = async () => {
      if (!user) return;

      try {
        // Refresh profile to get updated role
        const profile = await authApi.getProfile();

        setUser({
          ...user,
          role: profile.role,
          subscriptionActive: profile.subscriptionActive,
          subscriptionExpiresAt: profile.subscriptionExpiresAt,
          roleAssignedAt: profile.roleAssignedAt,
        });
      } catch (error) {
        console.warn('[useAuthBroadcast] Failed to refresh profile:', error);
      }
    };

    // Handle sign out from other tabs
    const handleSignOut = () => {
      // Reset auth state (the other tab already called the API)
      useAuthStore.getState().reset();
    };

    // Handle refresh request from other tabs
    const handleRefresh = async () => {
      if (!user) return;

      try {
        const profile = await authApi.getProfile();
        setUser({
          ...user,
          ...profile,
        });
      } catch (error) {
        console.warn('[useAuthBroadcast] Failed to refresh profile:', error);
      }
    };

    broadcastSync.on('ROLE_UPGRADED', handleRoleUpgraded);
    broadcastSync.on('SIGN_OUT', handleSignOut);
    broadcastSync.on('REFRESH', handleRefresh);

    return () => {
      broadcastSync.off('ROLE_UPGRADED', handleRoleUpgraded);
      broadcastSync.off('SIGN_OUT', handleSignOut);
      broadcastSync.off('REFRESH', handleRefresh);
      broadcastSync.disconnect();
    };
  }, [setUser, user]);
}
