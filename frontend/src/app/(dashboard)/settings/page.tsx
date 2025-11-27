'use client';

import { motion } from 'framer-motion';
import { User, Bell, Moon, Vibrate, LogOut } from 'lucide-react';
import { PageTransition } from '@/components/layout/page-transition';
import { Card } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { useAnimationStore } from '@/stores/animation-store';
import { cn } from '@/lib/utils';

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

  return (
    <PageTransition>
      <div className="space-y-6 max-w-2xl mx-auto">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-foreground md:hidden">Settings</h1>
          <p className="text-muted-foreground mt-1">Customize your dashboard experience</p>
        </div>

        {/* Profile section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="p-4">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
              Profile
            </h2>
            <SettingItem
              icon={User}
              label="Account"
              description="Manage your account settings"
            >
              <Button variant="outline" size="sm">
                Edit
              </Button>
            </SettingItem>
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
          <Card className="p-4">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
              Notifications
            </h2>

            <SettingItem
              icon={Bell}
              label="Push Notifications"
              description="Receive alerts on your device"
            >
              <Switch disabled />
            </SettingItem>

            <SettingItem
              icon={Bell}
              label="Email Notifications"
              description="Receive alerts via email"
            >
              <Switch disabled />
            </SettingItem>
          </Card>
        </motion.div>

        {/* Sign out */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <Button
            variant="outline"
            className="w-full gap-2 text-red-500 border-red-500/20 hover:bg-red-500/10"
          >
            <LogOut className="w-4 h-4" />
            Sign Out
          </Button>
        </motion.div>
      </div>
    </PageTransition>
  );
}
