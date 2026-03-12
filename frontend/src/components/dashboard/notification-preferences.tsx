'use client';

import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Bell, Mail, Clock, AlertCircle, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface NotificationSettings {
  emailEnabled: boolean;
  emailDigestFrequency: 'realtime' | 'daily' | 'weekly';
  quietHoursEnabled: boolean;
  quietHoursStart: string;
  quietHoursEnd: string;
}

interface NotificationPreferencesProps {
  initialSettings?: Partial<NotificationSettings>;
  onSave?: (settings: NotificationSettings) => Promise<void>;
  isLoading?: boolean;
  className?: string;
}

const defaultSettings: NotificationSettings = {
  emailEnabled: true,
  emailDigestFrequency: 'realtime',
  quietHoursEnabled: false,
  quietHoursStart: '22:00',
  quietHoursEnd: '08:00',
};

export function NotificationPreferences({
  initialSettings,
  onSave,
  isLoading = false,
  className,
}: NotificationPreferencesProps) {
  const [settings, setSettings] = useState<NotificationSettings>({
    ...defaultSettings,
    ...initialSettings,
  });
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const updateSetting = useCallback(
    <K extends keyof NotificationSettings>(key: K, value: NotificationSettings[K]) => {
      setSettings((prev) => ({ ...prev, [key]: value }));
      setIsDirty(true);
      setSaveSuccess(false);
    },
    []
  );

  const handleSave = useCallback(async () => {
    if (!onSave) return;

    setIsSaving(true);
    try {
      await onSave(settings);
      setIsDirty(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
    } catch (error) {
      // Error handled by parent
    } finally {
      setIsSaving(false);
    }
  }, [onSave, settings]);

  return (
    <div className={cn('space-y-4', className)}>
      {/* Email notifications */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-accent/10 flex items-center justify-center">
              <Mail className="w-5 h-5 text-accent" />
            </div>
            <div>
              <p className="font-medium text-foreground">Email Notifications</p>
              <p className="text-sm text-muted-foreground">
                Receive alerts when thresholds are crossed
              </p>
            </div>
          </div>
          <Switch
            checked={settings.emailEnabled}
            onCheckedChange={(checked) => updateSetting('emailEnabled', checked)}
            disabled={isLoading}
            aria-label="Email Notifications"
          />
        </div>

        {/* Frequency selector */}
        {settings.emailEnabled && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="pt-4 border-t border-border"
          >
            <p className="text-sm font-medium text-foreground mb-3">
              Notification Frequency
            </p>
            <div className="grid grid-cols-3 gap-2">
              {(['realtime', 'daily', 'weekly'] as const).map((freq) => (
                <button
                  key={freq}
                  type="button"
                  onClick={() => updateSetting('emailDigestFrequency', freq)}
                  disabled={isLoading}
                  className={cn(
                    'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                    settings.emailDigestFrequency === freq
                      ? 'bg-accent text-accent-foreground'
                      : 'bg-muted text-muted-foreground hover:bg-muted/80'
                  )}
                >
                  {freq === 'realtime' ? 'Real-time' : freq.charAt(0).toUpperCase() + freq.slice(1)}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {settings.emailDigestFrequency === 'realtime'
                ? 'Get notified immediately when alerts trigger'
                : settings.emailDigestFrequency === 'daily'
                ? 'Receive a daily summary at 8 AM'
                : 'Receive a weekly summary on Mondays'}
            </p>
          </motion.div>
        )}
      </Card>

      {/* Quiet hours */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
              <Clock className="w-5 h-5 text-muted-foreground" />
            </div>
            <div>
              <p className="font-medium text-foreground">Quiet Hours</p>
              <p className="text-sm text-muted-foreground">
                Pause notifications during set hours
              </p>
            </div>
          </div>
          <Switch
            checked={settings.quietHoursEnabled}
            onCheckedChange={(checked) => updateSetting('quietHoursEnabled', checked)}
            disabled={isLoading}
            aria-label="Quiet Hours"
          />
        </div>

        {/* Time selectors */}
        {settings.quietHoursEnabled && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="pt-4 border-t border-border"
          >
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <label className="text-sm text-muted-foreground mb-1 block">
                  Start
                </label>
                <input
                  type="time"
                  value={settings.quietHoursStart}
                  onChange={(e) => updateSetting('quietHoursStart', e.target.value)}
                  disabled={isLoading}
                  className="w-full px-3 py-2 rounded-md border border-border bg-background text-foreground"
                />
              </div>
              <div className="flex-1">
                <label className="text-sm text-muted-foreground mb-1 block">
                  End
                </label>
                <input
                  type="time"
                  value={settings.quietHoursEnd}
                  onChange={(e) => updateSetting('quietHoursEnd', e.target.value)}
                  disabled={isLoading}
                  className="w-full px-3 py-2 rounded-md border border-border bg-background text-foreground"
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Notifications will be held and delivered when quiet hours end
            </p>
          </motion.div>
        )}
      </Card>

      {/* Save button */}
      {onSave && (
        <div className="flex items-center justify-between">
          {isDirty && (
            <p className="text-sm text-muted-foreground">
              <AlertCircle className="w-4 h-4 inline mr-1" />
              Unsaved changes
            </p>
          )}
          {saveSuccess && (
            <p className="text-sm text-green-500">
              <Check className="w-4 h-4 inline mr-1" />
              Settings saved
            </p>
          )}
          <Button
            onClick={handleSave}
            disabled={!isDirty || isSaving}
            className="ml-auto"
          >
            {isSaving ? (
              <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              'Save Changes'
            )}
          </Button>
        </div>
      )}
    </div>
  );
}

// Simple toggle for inline use
interface NotificationToggleProps {
  label: string;
  description?: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
}

export function NotificationToggle({
  label,
  description,
  checked,
  onCheckedChange,
  disabled = false,
  className,
}: NotificationToggleProps) {
  return (
    <div className={cn('flex items-center justify-between py-3', className)}>
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
          <Bell className="w-4 h-4 text-muted-foreground" />
        </div>
        <div>
          <p className="font-medium text-sm text-foreground">{label}</p>
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
          )}
        </div>
      </div>
      <Switch checked={checked} onCheckedChange={onCheckedChange} disabled={disabled} />
    </div>
  );
}
