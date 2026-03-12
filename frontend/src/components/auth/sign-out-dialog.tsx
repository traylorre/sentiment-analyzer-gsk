'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { LogOut, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/use-auth';
import { cn } from '@/lib/utils';

interface SignOutDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SignOutDialog({ open, onOpenChange }: SignOutDialogProps) {
  const { signOut, isLoading, isAnonymous } = useAuth();
  const [isSigningOut, setIsSigningOut] = useState(false);

  const handleSignOut = async () => {
    try {
      setIsSigningOut(true);
      await signOut();
      window.location.href = '/';
    } catch {
      // Error handled by auth store
      setIsSigningOut(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => onOpenChange(false)}
          />

          {/* Dialog */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="sign-out-dialog-title"
            className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 p-4"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2 }}
          >
            <div className="rounded-lg border border-border bg-background shadow-lg">
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b border-border">
                <h2 id="sign-out-dialog-title" className="text-lg font-semibold text-foreground">
                  Sign out
                </h2>
                <button
                  onClick={() => onOpenChange(false)}
                  className="p-1 rounded-md hover:bg-muted transition-colors"
                >
                  <X className="w-5 h-5 text-muted-foreground" />
                </button>
              </div>

              {/* Content */}
              <div className="p-4 space-y-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center">
                    <LogOut className="w-6 h-6 text-red-500" />
                  </div>
                  <div>
                    <p className="text-foreground">
                      Are you sure you want to sign out?
                    </p>
                    {isAnonymous && (
                      <p className="text-sm text-amber-500 mt-1">
                        Warning: As a guest, your configurations will be lost.
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="flex gap-3 p-4 border-t border-border">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => onOpenChange(false)}
                  disabled={isSigningOut}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  className="flex-1 gap-2"
                  onClick={handleSignOut}
                  disabled={isSigningOut || isLoading}
                >
                  {isSigningOut ? (
                    <>
                      <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                      Signing out...
                    </>
                  ) : (
                    <>
                      <LogOut className="w-4 h-4" />
                      Sign out
                    </>
                  )}
                </Button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// Trigger component for use in menus
interface SignOutButtonProps {
  className?: string;
  variant?: 'default' | 'ghost' | 'destructive';
}

export function SignOutButton({ className, variant = 'ghost' }: SignOutButtonProps) {
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <>
      <Button
        variant={variant}
        className={cn('gap-2', className)}
        onClick={() => setDialogOpen(true)}
      >
        <LogOut className="w-4 h-4" />
        Sign out
      </Button>
      <SignOutDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </>
  );
}
