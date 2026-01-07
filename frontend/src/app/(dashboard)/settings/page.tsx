'use client';

import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { User, Bell, Moon, Vibrate, LogOut, Shield, Mail } from 'lucide-react';
import { PageTransition } from '@/components/layout/page-transition';
import { Card } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { NotificationPreferences } from '@/components/dashboard/notification-preferences';
import { SignOutDialog } from '@/components/auth/sign-out-dialog';
import { useAnimationStore } from '@/stores/animation-store';
import { useAuth } from '@/hooks/use-auth';
import { cn } from '@/lib/utils';
import { notificationsApi } from '@/lib/api';

interface SettingItemProps {
  icon: typeof User;
  label: string;
  description?: string;
  children: React.ReactNode;
}

function SettingItem({ icon: Icon, label, description, children }: SettingItemProps) {
  return (
    <div className="flex items-center justify-between py-4 border-b border-border last:border-0">
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
          <Icon className="w-5 h-5 text-muted-foreground" />
        </div>
        <div>
          <p className="font-medium text-foreground">{label}</p>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
      </div>
      {children}
    </div>
  );
}

export default function SettingsPage() {
  const { reducedMotion, hapticEnabled, setReducedMotion, setHapticEnabled } = useAnimationStore();
  // Feature 1165: Use isInitialized instead of hasHydrated (memory-only store)
  const { isInitialized, user, isAuthenticated, isAnonymous, signOut, isLoading } = useAuth();
  const [signOutOpen, setSignOutOpen] = useState(false);

  // All hooks must be called before early returns (React rules of hooks)
  const handleNotificationSave = useCallback(async (settings: { emailEnabled: boolean }) => {
    await notificationsApi.updatePreferences({
      email_enabled: settings.emailEnabled,
    });
  }, []);

  // Feature 1165: Show skeleton/loading state until initialized
  if (!isInitialized) {
    return (
      <PageTransition>
        <div className="space-y-6 max-w-2xl mx-auto">
          <div>
            <div className="h-8 w-32 bg-muted rounded animate-pulse md:hidden" />
            <div className="h-5 w-64 bg-muted rounded animate-pulse mt-1" />
          </div>
          <div className="h-48 bg-muted rounded-lg animate-pulse" />
          <div className="h-32 bg-muted rounded-lg animate-pulse" />
        </div>
      </PageTransition>
    );
  }

  const authTypeLabel: Record<string, string> = {
    anonymous: 'Anonymous',
    email: 'Email',
    google: 'Google',
    github: 'GitHub',
  };

  return (
    <PageTransition>
      <div className="space-y-6 max-w-2xl mx-auto">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-foreground md:hidden">Settings</h1>
          <p className="text-muted-foreground mt-1">Customize your dashboard experience</p>
        </div>

        {/* Account section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="p-4">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
              Account
            </h2>

            {isAuthenticated && user ? (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center">
                    <User className="w-6 h-6 text-accent" />
                  </div>
                  <div>
                    {user.email && (
                      <p className="font-medium text-foreground">{user.email}</p>
                    )}
                    <div className="flex items-center gap-2 mt-1">
                      <span
                        className={cn(
                          'px-2 py-0.5 text-xs rounded-full',
                          isAnonymous
                            ? 'bg-muted text-muted-foreground'
                            : 'bg-accent/10 text-accent'
                        )}
                      >
                        {authTypeLabel[user.authType] || user.authType}
                      </span>
                      {isAnonymous && (
                        <span className="text-xs text-muted-foreground">
                          (limited features)
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {isAnonymous && (
                  <div className="p-3 rounded-lg bg-accent/5 border border-accent/20">
                    <p className="text-sm text-foreground mb-2">
                      <Shield className="w-4 h-4 inline mr-2" />
                      Upgrade your account
                    </p>
                    <p className="text-xs text-muted-foreground mb-3">
                      Sign in with email or social to unlock all features and save
                      your data across devices.
                    </p>
                    <Button size="sm" className="gap-2">
                      <Mail className="w-4 h-4" />
                      Upgrade Now
                    </Button>
                  </div>
                )}

                <div className="text-xs text-muted-foreground">
                  <p>
                    <strong>Configurations:</strong> {user.configurationCount}
                  </p>
                  <p>
                    <strong>Alerts:</strong> {user.alertCount}
                  </p>
                  <p>
                    <strong>Member since:</strong>{' '}
                    {new Date(user.createdAt).toLocaleDateString()}
                  </p>
                </div>
              </div>
            ) : (
              <SettingItem
                icon={User}
                label="Account"
                description="Sign in to save your settings"
              >
                <Button variant="outline" size="sm">
                  Sign In
                </Button>
              </SettingItem>
            )}
          </Card>
        </motion.div>

        {/* Preferences section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card className="p-4">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
              Preferences
            </h2>

            <SettingItem
              icon={Moon}
              label="Dark Mode"
              description="Always on (system default)"
            >
              <Switch checked disabled />
            </SettingItem>

            <SettingItem
              icon={Vibrate}
              label="Haptic Feedback"
              description="Vibration on touch interactions"
            >
              <Switch
                id="haptic"
                checked={hapticEnabled}
                onCheckedChange={setHapticEnabled}
              />
            </SettingItem>

            <SettingItem
              icon={Bell}
              label="Reduced Motion"
              description="Minimize animations"
            >
              <Switch
                id="reduced-motion"
                checked={reducedMotion}
                onCheckedChange={setReducedMotion}
              />
            </SettingItem>
          </Card>
        </motion.div>

        {/* Notifications section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
            Notifications
          </h2>
          <NotificationPreferences
            initialSettings={{
              emailEnabled: user?.emailNotificationsEnabled ?? true,
            }}
            onSave={handleNotificationSave}
          />
        </motion.div>

        {/* Sign out */}
        {isAuthenticated && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Button
              variant="outline"
              className="w-full gap-2 text-red-500 border-red-500/20 hover:bg-red-500/10"
              onClick={() => setSignOutOpen(true)}
            >
              <LogOut className="w-4 h-4" />
              Sign Out
            </Button>
            <SignOutDialog
              open={signOutOpen}
              onOpenChange={setSignOutOpen}
            />
          </motion.div>
        )}
      </div>
    </PageTransition>
  );
}
