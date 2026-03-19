'use client';

import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import {
  useApiHealthStore,
  selectBannerVisible,
  selectFailureCount,
} from '@/stores/api-health-store';
import { emitErrorEvent } from '@/lib/api/client';

/**
 * Feature 1226: API Health Banner (FR-005)
 *
 * Fixed-position warning banner shown when the API is detected as unreachable.
 * Dismissible by the user; auto-clears when connectivity recovers.
 *
 * Console events emitted for Playwright test assertions:
 *   - api_health_banner_shown: Banner became visible
 *   - api_health_banner_dismissed: User clicked dismiss
 *   - api_health_recovered: Transitioned from unreachable to healthy
 */
export function ApiHealthBanner() {
  const bannerVisible = useApiHealthStore(selectBannerVisible);
  const failureCount = useApiHealthStore(selectFailureCount);
  const dismissBanner = useApiHealthStore((state) => state.dismissBanner);
  const isUnreachable = useApiHealthStore((state) => state.isUnreachable);

  // Track previous unreachable state to detect recovery transitions
  const prevUnreachableRef = useRef(false);

  // Emit console event when banner becomes visible
  useEffect(() => {
    if (bannerVisible) {
      emitErrorEvent('api_health_banner_shown', { failureCount });
    }
  }, [bannerVisible, failureCount]);

  // Detect recovery: unreachable -> healthy
  useEffect(() => {
    if (prevUnreachableRef.current && !isUnreachable) {
      emitErrorEvent('api_health_recovered', {});
    }
    prevUnreachableRef.current = isUnreachable;
  }, [isUnreachable]);

  if (!bannerVisible) {
    return null;
  }

  const handleDismiss = () => {
    emitErrorEvent('api_health_banner_dismissed', {});
    dismissBanner();
  };

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 py-2 bg-amber-900/90 border-b border-amber-700 text-amber-100 text-sm"
    >
      <span>
        We&apos;re having trouble connecting to the server. Some features may be
        unavailable.
      </span>
      <button
        onClick={handleDismiss}
        className="ml-4 p-1 rounded hover:bg-amber-800 transition-colors flex-shrink-0"
        aria-label="Dismiss connectivity warning"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
