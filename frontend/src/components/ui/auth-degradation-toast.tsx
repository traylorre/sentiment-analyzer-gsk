'use client';

import { useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { useAuthStore } from '@/stores/auth-store';

/**
 * User Story 3: Auth degradation toast notification.
 * Watches sessionDegraded and shows a warning toast on false->true transition
 * for authenticated (non-anonymous) users.
 */
export function AuthDegradationToast() {
  const sessionDegraded = useAuthStore((state) => state.sessionDegraded);
  const user = useAuthStore((state) => state.user);
  const prevDegradedRef = useRef(false);

  useEffect(() => {
    const wasDegraded = prevDegradedRef.current;
    prevDegradedRef.current = sessionDegraded;

    // Only fire on false -> true transition
    if (!wasDegraded && sessionDegraded) {
      // Only show for authenticated, non-anonymous users
      if (user && user.authType !== 'anonymous') {
        toast.warning('Your session may expire soon. Please save your work.', {
          action: {
            label: 'Sign in again',
            onClick: () => {
              window.location.href = '/auth/signin';
            },
          },
          duration: Infinity,
        });
      }
    }
  }, [sessionDegraded, user]);

  return null;
}
