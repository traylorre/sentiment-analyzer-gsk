'use client';

import { useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { alertsApi, type UpdateAlertRequest } from '@/lib/api/alerts';
import type { AlertRule, CreateAlertRequest, Notification } from '@/types/alert';

const ALERTS_QUERY_KEY = ['alerts'];
const NOTIFICATIONS_QUERY_KEY = ['notifications'];

export function useAlerts(configId?: string) {
  const queryClient = useQueryClient();

  // Fetch alerts
  const {
    data,
    isLoading: isFetching,
    error: fetchError,
    refetch,
  } = useQuery({
    queryKey: configId ? [...ALERTS_QUERY_KEY, configId] : ALERTS_QUERY_KEY,
    queryFn: async () => {
      const result = configId
        ? await alertsApi.listByConfig(configId)
        : await alertsApi.list();
      return result;
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (alert: CreateAlertRequest) => alertsApi.create(alert),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ALERTS_QUERY_KEY });
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ alertId, updates }: { alertId: string; updates: UpdateAlertRequest }) =>
      alertsApi.update(alertId, updates),
    onMutate: async ({ alertId, updates }) => {
      // Cancel outgoing fetches
      await queryClient.cancelQueries({ queryKey: ALERTS_QUERY_KEY });

      // Snapshot previous value
      const previousData = queryClient.getQueryData(
        configId ? [...ALERTS_QUERY_KEY, configId] : ALERTS_QUERY_KEY
      );

      // Optimistically update
      queryClient.setQueryData(
        configId ? [...ALERTS_QUERY_KEY, configId] : ALERTS_QUERY_KEY,
        (old: typeof data) => {
          if (!old) return old;
          return {
            ...old,
            alerts: old.alerts.map((alert: AlertRule) =>
              alert.alertId === alertId ? { ...alert, ...updates } : alert
            ),
          };
        }
      );

      return { previousData };
    },
    onError: (_err, _vars, context) => {
      // Rollback on error
      if (context?.previousData) {
        queryClient.setQueryData(
          configId ? [...ALERTS_QUERY_KEY, configId] : ALERTS_QUERY_KEY,
          context.previousData
        );
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ALERTS_QUERY_KEY });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (alertId: string) => alertsApi.delete(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ALERTS_QUERY_KEY });
    },
  });

  // Toggle alert enabled state
  const toggleAlert = useCallback(
    (alertId: string, isEnabled: boolean) => {
      updateMutation.mutate({ alertId, updates: { isEnabled } });
    },
    [updateMutation]
  );

  // Actions
  const createAlert = useCallback(
    (alert: CreateAlertRequest) => createMutation.mutateAsync(alert),
    [createMutation]
  );

  const updateAlert = useCallback(
    (alertId: string, updates: UpdateAlertRequest) =>
      updateMutation.mutateAsync({ alertId, updates }),
    [updateMutation]
  );

  const deleteAlert = useCallback(
    (alertId: string) => deleteMutation.mutateAsync(alertId),
    [deleteMutation]
  );

  return {
    // Data
    alerts: data?.alerts ?? [],
    total: data?.total ?? 0,
    dailyEmailQuota: data?.dailyEmailQuota ?? { used: 0, limit: 100, resetsAt: '' },

    // Loading states
    isLoading: isFetching,
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,

    // Errors
    error: fetchError?.message || createMutation.error?.message || null,

    // Actions
    refetch,
    createAlert,
    updateAlert,
    deleteAlert,
    toggleAlert,
  };
}

// Hook for notification history
export function useNotifications(limit: number = 10) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: [...NOTIFICATIONS_QUERY_KEY, limit],
    queryFn: () => alertsApi.getNotifications(limit),
    staleTime: 60 * 1000, // 1 minute
  });

  return {
    notifications: data ?? [],
    isLoading,
    error: error?.message || null,
    refetch,
  };
}

// Hook for a single alert with config context
export function useAlert(alertId: string | null) {
  const { data: alert, isLoading } = useQuery({
    queryKey: ['alert', alertId],
    queryFn: () => (alertId ? alertsApi.get(alertId) : null),
    enabled: !!alertId,
    staleTime: 60 * 1000,
  });

  return {
    alert,
    isLoading,
  };
}
