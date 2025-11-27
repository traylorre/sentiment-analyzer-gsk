'use client';

import { useEffect, type ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Loader2, Lock } from 'lucide-react';
import { useAuth } from '@/hooks/use-auth';
import { Button } from '@/components/ui/button';
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
  const { isAuthenticated, isAnonymous, isLoading, isInitialized } = useAuth();

  const hasAccess = requireUpgraded
    ? isAuthenticated && !isAnonymous
    : requireAuth
    ? isAuthenticated
    : true;

  useEffect(() => {
    if (isInitialized && !isLoading && !hasAccess) {
      router.push(redirectTo);
    }
  }, [isInitialized, isLoading, hasAccess, router, redirectTo]);

  // Show loading state while checking auth
  if (!isInitialized || isLoading) {
    return (
      <div className={cn('min-h-[400px] flex items-center justify-center', className)}>
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

  // Show upgrade prompt if anonymous but need upgraded
  if (requireUpgraded && isAnonymous) {
    return (
      <div className={cn('min-h-[400px] flex items-center justify-center', className)}>
        <motion.div
          className="text-center space-y-4 max-w-sm"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="w-16 h-16 mx-auto rounded-full bg-accent/10 flex items-center justify-center">
            <Lock className="w-8 h-8 text-accent" />
          </div>
          <h3 className="text-xl font-semibold text-foreground">
            Sign in required
          </h3>
          <p className="text-muted-foreground">
            Please sign in with your email to access this feature.
          </p>
          <Button onClick={() => router.push(redirectTo)}>
            Sign in
          </Button>
        </motion.div>
      </div>
    );
  }

  // Show children if access granted
  if (hasAccess) {
    return <>{children}</>;
  }

  // Default: redirect in progress
  return null;
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
  const { isAuthenticated, isAnonymous } = useAuth();

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
