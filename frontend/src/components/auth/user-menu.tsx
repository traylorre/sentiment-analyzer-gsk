'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  User,
  Settings,
  LogOut,
  ChevronDown,
  Mail,
  Shield,
  Clock,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/use-auth';
import { cn } from '@/lib/utils';

interface UserMenuProps {
  className?: string;
}

// T019: Skeleton component for UserMenu during hydration (FR-017)
function UserMenuSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      {/* Animated shimmer placeholder matching UserMenu button dimensions */}
      <div className="w-8 h-8 rounded-full bg-muted animate-pulse" />
      <div className="hidden sm:block w-16 h-4 rounded bg-muted animate-pulse" />
      <div className="w-4 h-4 rounded bg-muted animate-pulse" />
    </div>
  );
}

export function UserMenu({ className }: UserMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  // T020: Include hasHydrated to show skeleton during hydration
  const { hasHydrated, user, isAuthenticated, isAnonymous, signOut, isLoading } = useAuth();

  // FR-017: Show skeleton during hydration to prevent sign-in button flash
  if (!hasHydrated) {
    return <UserMenuSkeleton className={className} />;
  }

  if (!isAuthenticated) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => (window.location.href = '/auth/signin')}
        className={className}
      >
        Sign in
      </Button>
    );
  }

  const displayName = isAnonymous
    ? 'Guest'
    : user?.email?.split('@')[0] || 'User';

  const authTypeLabels: Record<string, string> = {
    anonymous: 'Guest',
    magic_link: 'Email',
    google: 'Google',
    github: 'GitHub',
  };
  const authTypeLabel = authTypeLabels[user?.authType || 'anonymous'];

  return (
    <div className={cn('relative', className)}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        className="gap-2"
      >
        <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center">
          <User className="w-4 h-4 text-accent" />
        </div>
        <span className="hidden sm:inline text-sm font-medium truncate max-w-[100px]">
          {displayName}
        </span>
        <ChevronDown
          className={cn(
            'w-4 h-4 transition-transform',
            isOpen && 'rotate-180'
          )}
        />
      </Button>

      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              className="fixed inset-0 z-40"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsOpen(false)}
            />

            {/* Menu */}
            <motion.div
              className="absolute right-0 top-full mt-2 w-64 z-50 rounded-lg border border-border bg-background/95 backdrop-blur-lg shadow-lg overflow-hidden"
              initial={{ opacity: 0, y: -10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.95 }}
              transition={{ duration: 0.15 }}
            >
              {/* User info section */}
              <div className="p-4 border-b border-border">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-accent/20 flex items-center justify-center">
                    <User className="w-5 h-5 text-accent" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-foreground truncate">
                      {displayName}
                    </p>
                    {user?.email && (
                      <p className="text-xs text-muted-foreground truncate">
                        {user.email}
                      </p>
                    )}
                  </div>
                </div>

                {/* Auth type badge */}
                <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                  <Shield className="w-3 h-3" />
                  <span>Signed in via {authTypeLabel}</span>
                </div>
              </div>

              {/* Menu items */}
              <div className="p-2">
                {isAnonymous && (
                  <MenuButton
                    icon={Mail}
                    label="Sign in with email"
                    onClick={() => {
                      setIsOpen(false);
                      window.location.href = '/auth/signin';
                    }}
                    highlight
                  />
                )}

                <MenuButton
                  icon={Settings}
                  label="Settings"
                  onClick={() => {
                    setIsOpen(false);
                    window.location.href = '/settings';
                  }}
                />

                <MenuButton
                  icon={LogOut}
                  label="Sign out"
                  onClick={() => {
                    setIsOpen(false);
                    signOut();
                  }}
                  disabled={isLoading}
                  danger
                />
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

interface MenuButtonProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  highlight?: boolean;
  danger?: boolean;
}

function MenuButton({
  icon: Icon,
  label,
  onClick,
  disabled,
  highlight,
  danger,
}: MenuButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
        'hover:bg-muted/50',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        highlight && 'text-accent hover:bg-accent/10',
        danger && 'text-red-500 hover:bg-red-500/10'
      )}
    >
      <Icon className="w-4 h-4" />
      <span>{label}</span>
    </button>
  );
}

// Session timer component
interface SessionTimerProps {
  className?: string;
}

export function SessionTimer({ className }: SessionTimerProps) {
  const { isSessionValid, remainingSessionMs, refreshSession, isLoading } = useAuth();

  if (!isSessionValid) {
    return null;
  }

  const formatTime = (ms: number) => {
    const minutes = Math.floor(ms / 60000);
    const seconds = Math.floor((ms % 60000) / 1000);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const isExpiringSoon = remainingSessionMs < 5 * 60 * 1000; // 5 minutes

  return (
    <div
      className={cn(
        'flex items-center gap-2 text-xs',
        isExpiringSoon ? 'text-amber-500' : 'text-muted-foreground',
        className
      )}
    >
      <Clock className="w-3 h-3" />
      <span>Session: {formatTime(remainingSessionMs)}</span>
      {isExpiringSoon && (
        <button
          onClick={() => refreshSession()}
          disabled={isLoading}
          className="text-accent hover:underline disabled:opacity-50"
        >
          Extend
        </button>
      )}
    </div>
  );
}
