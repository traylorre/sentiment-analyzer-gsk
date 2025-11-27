'use client';

import { useState, useCallback } from 'react';
import { PageTransition } from '@/components/layout/page-transition';
import { AlertList, AlertSummary } from '@/components/dashboard/alert-list';
import { AlertForm } from '@/components/dashboard/alert-form';
import { RecentTriggers, NotificationCard } from '@/components/dashboard/trigger-badge';
import { DeleteConfirmation } from '@/components/dashboard/delete-confirmation';
import { useAlerts, useNotifications } from '@/hooks/use-alerts';
import { useConfigs } from '@/hooks/use-configs';
import type { AlertRule, CreateAlertRequest } from '@/types/alert';

export default function AlertsPage() {
  const { configurations } = useConfigs();
  const {
    alerts,
    dailyEmailQuota,
    isLoading,
    isCreating,
    createAlert,
    toggleAlert,
    deleteAlert,
  } = useAlerts();
  const { notifications } = useNotifications(5);

  // UI state
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingAlert, setEditingAlert] = useState<AlertRule | null>(null);
  const [deletingAlertId, setDeletingAlertId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Handle form submit
  const handleFormSubmit = useCallback(
    async (data: CreateAlertRequest) => {
      try {
        await createAlert(data);
        setIsFormOpen(false);
        setEditingAlert(null);
      } catch (error) {
        // Error handled by mutation
      }
    },
    [createAlert]
  );

  // Handle edit
  const handleEdit = useCallback((alert: AlertRule) => {
    setEditingAlert(alert);
    setIsFormOpen(true);
  }, []);

  // Handle delete confirmation
  const handleDeleteConfirm = useCallback(async () => {
    if (deletingAlertId) {
      setIsDeleting(true);
      try {
        await deleteAlert(deletingAlertId);
        setDeletingAlertId(null);
      } catch (error) {
        // Error handled by mutation
      } finally {
        setIsDeleting(false);
      }
    }
  }, [deletingAlertId, deleteAlert]);

  // Find alert being deleted
  const deletingAlert = deletingAlertId
    ? alerts.find((a) => a.alertId === deletingAlertId)
    : null;

  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header - only show on mobile */}
        <div className="md:hidden">
          <h1 className="text-2xl font-bold text-foreground">Alerts</h1>
          <p className="text-muted-foreground mt-1">
            Manage your sentiment alert rules
          </p>
        </div>

        {/* Summary stats */}
        {alerts.length > 0 && <AlertSummary alerts={alerts} />}

        {/* Recent triggers */}
        {notifications.length > 0 && (
          <RecentTriggers notifications={notifications} />
        )}

        {/* Alert list */}
        <AlertList
          alerts={alerts}
          dailyEmailQuota={dailyEmailQuota}
          isLoading={isLoading}
          onToggle={toggleAlert}
          onEdit={handleEdit}
          onDelete={setDeletingAlertId}
          onCreate={() => setIsFormOpen(true)}
        />

        {/* Create/Edit form modal */}
        <AlertForm
          isOpen={isFormOpen}
          editingAlert={editingAlert}
          configurations={configurations}
          onClose={() => {
            setIsFormOpen(false);
            setEditingAlert(null);
          }}
          onSubmit={handleFormSubmit}
          isLoading={isCreating}
        />

        {/* Delete confirmation dialog */}
        <DeleteConfirmation
          isOpen={!!deletingAlertId}
          itemName={
            deletingAlert
              ? `${deletingAlert.ticker} ${deletingAlert.alertType === 'sentiment_threshold' ? 'sentiment' : 'volatility'} alert`
              : ''
          }
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeletingAlertId(null)}
          isDeleting={isDeleting}
        />
      </div>
    </PageTransition>
  );
}
