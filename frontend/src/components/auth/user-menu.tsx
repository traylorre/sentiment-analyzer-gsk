'use client';

import { useState } from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
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
  // Feature 1165: Use isInitialized instead of hasHydrated (memory-only store)
  const { isInitialized, user, isAuthenticated, isAnonymous, signOut, isLoading } = useAuth();

  // Feature 1165: Show skeleton until initialized to prevent sign-in button flash
  if (!isInitialized) {
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
    <DropdownMenu.Root open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenu.Trigger asChild>
        <Button
          variant="ghost"
          size="sm"
          data-testid="user-menu-trigger"
          className={cn('gap-2', className)}
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
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className="w-64 z-50 rounded-lg border border-border bg-background/95 backdrop-blur-lg shadow-lg overflow-hidden data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=top]:slide-in-from-bottom-2 data-[side=bottom]:slide-in-from-top-2"
          side="top"
          align="start"
          sideOffset={8}
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
              <DropdownMenu.Item
                className="flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors text-accent hover:bg-accent/10 cursor-pointer outline-none data-[highlighted]:bg-accent/10"
                onSelect={() => {
                  window.location.href = '/auth/signin';
                }}
              >
                <Mail className="w-4 h-4" />
                <span>Sign in with email</span>
              </DropdownMenu.Item>
            )}

            <DropdownMenu.Item
              className="flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors hover:bg-muted/50 cursor-pointer outline-none data-[highlighted]:bg-muted/50"
              onSelect={() => {
                window.location.href = '/settings';
              }}
            >
              <Settings className="w-4 h-4" />
              <span>Settings</span>
            </DropdownMenu.Item>

            <DropdownMenu.Item
              className="flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors text-red-500 hover:bg-red-500/10 cursor-pointer outline-none data-[highlighted]:bg-red-500/10 data-[disabled]:opacity-50 data-[disabled]:cursor-not-allowed"
              onSelect={() => {
                signOut();
              }}
              disabled={isLoading}
            >
              <LogOut className="w-4 h-4" />
              <span>Sign out</span>
            </DropdownMenu.Item>
          </div>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

// Session timer component (separate export — NOT inside DropdownMenu)
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
