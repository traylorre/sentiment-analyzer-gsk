'use client';

import { useEffect, type ReactNode } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import { Loader2, Lock } from 'lucide-react';
import { useAuth } from '@/hooks/use-auth';
import { cn } from '@/lib/utils';

interface ProtectedRouteProps {
  children: ReactNode;
  requireAuth?: boolean;
  requireUpgraded?: boolean; // Requires non-anonymous auth
  fallback?: ReactNode;
  redirectTo?: string;
  className?: string;
}

export function ProtectedRoute({
  children,
  requireAuth = true,
  requireUpgraded = false,
  fallback,
  redirectTo = '/auth/signin',
  className,
}: ProtectedRouteProps) {
  const router = useRouter();
  const pathname = usePathname();
  // Feature 1165: Use isInitialized instead of hasHydrated (memory-only store)
  const { isAuthenticated, isAnonymous, isLoading, isInitialized } = useAuth();

  const hasAccess = requireUpgraded
    ? isAuthenticated && !isAnonymous
    : requireAuth
    ? isAuthenticated
    : true;

  // M1 WI-5: preserve the old middleware redirect contract:
  // /auth/signin?redirect=<origin path>&upgrade=true (upgrade only when the
  // route needs a non-anonymous session).
  const params = new URLSearchParams({ redirect: pathname });
  if (requireUpgraded) {
    params.set('upgrade', 'true');
  }
  const redirectUrl = `${redirectTo}?${params.toString()}`;

  // Feature 1165: Only redirect after initialized + auth check fails.
  // M1 WI-5: replace, not push — a history entry for the gated page would
  // bounce the user right back here on Back (the old middleware 302 left no
  // entry either).
  useEffect(() => {
    if (isInitialized && !isLoading && !hasAccess && !fallback) {
      router.replace(redirectUrl);
    }
  }, [isInitialized, isLoading, hasAccess, router, redirectUrl, fallback]);

  // Feature 1165: Show loading state until initialized
  if (!isInitialized || isLoading) {
    return (
      <div className={cn('min-h-[400px] flex items-center justify-center', className)} role="status" aria-label="Loading">
        <motion.div
          className="text-center space-y-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <Loader2 className="w-8 h-8 mx-auto text-accent animate-spin" />
          <p className="text-muted-foreground">Loading...</p>
        </motion.div>
      </div>
    );
  }

  // Show fallback if provided and no access
  if (!hasAccess && fallback) {
    return <>{fallback}</>;
  }

  // Show children if access granted
  if (hasAccess) {
    return <>{children}</>;
  }

  // M1 WI-5: redirect in progress (router.replace fired in the effect above).
  // The old inline "Sign in required" prompt was removed: it rendered AND the
  // effect redirected, so users saw a prompt flash before navigation. Q-M1-2
  // resolved to redirect semantics; pass `fallback` to opt out of redirecting.
  return (
    <div className={cn('min-h-[400px] flex items-center justify-center', className)} role="status" aria-label="Redirecting to sign in">
      <Loader2 className="w-8 h-8 text-accent animate-spin" />
    </div>
  );
}

// Higher-order component version
export function withProtectedRoute<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  options?: Omit<ProtectedRouteProps, 'children'>
) {
  return function ProtectedComponent(props: P) {
    return (
      <ProtectedRoute {...options}>
        <WrappedComponent {...props} />
      </ProtectedRoute>
    );
  };
}

// Auth guard for specific features
interface AuthGuardProps {
  children: ReactNode;
  feature?: 'alerts' | 'configs' | 'settings';
  fallback?: ReactNode;
}

export function AuthGuard({ children, feature, fallback }: AuthGuardProps) {
  // Feature 1165: Use isInitialized instead of hasHydrated (memory-only store)
  const { isInitialized, isAuthenticated, isAnonymous } = useAuth();

  // Don't render anything meaningful until initialized - parent handles loading state
  if (!isInitialized) {
    return null;
  }

  // Define which features require upgraded auth
  const requiresUpgrade = feature === 'alerts';

  if (requiresUpgrade && isAnonymous) {
    return (
      fallback || (
        <div className="p-6 text-center bg-muted/50 rounded-lg">
          <Lock className="w-6 h-6 mx-auto mb-2 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Sign in to access {feature}
          </p>
        </div>
      )
    );
  }

  if (!isAuthenticated) {
    return fallback || null;
  }

  return <>{children}</>;
}
