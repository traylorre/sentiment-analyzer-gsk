'use client';

import { useCallback, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { configsApi } from '@/lib/api/configs';
import { useConfigStore } from '@/stores/config-store';
import type { Configuration, CreateConfigRequest, UpdateConfigRequest } from '@/types/config';

const CONFIGS_QUERY_KEY = ['configurations'];

export function useConfigs() {
  const queryClient = useQueryClient();
  const {
    configurations,
    activeConfigId,
    isFormOpen,
    editingConfig,
    deletingConfigId,
    pendingDeletes,
    setConfigurations,
    addConfiguration,
    updateConfiguration,
    removeConfiguration,
    setActiveConfig,
    openCreateForm,
    openEditForm,
    closeForm,
    startDelete,
    cancelDelete,
    confirmDelete,
    markPendingDelete,
    unmarkPendingDelete,
    setLoading,
    setError,
  } = useConfigStore();

  // Fetch configurations
  const {
    data,
    isLoading: isFetching,
    error: fetchError,
    refetch,
  } = useQuery({
    queryKey: CONFIGS_QUERY_KEY,
    queryFn: async () => {
      const result = await configsApi.list();
      return result;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Sync fetched data to store
  useEffect(() => {
    if (data?.configurations) {
      setConfigurations(data.configurations);
    }
  }, [data, setConfigurations]);

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (config: CreateConfigRequest) => configsApi.create(config),
    onSuccess: (newConfig) => {
      addConfiguration(newConfig);
      queryClient.invalidateQueries({ queryKey: CONFIGS_QUERY_KEY });
      closeForm();
    },
    onError: (error) => {
      setError(error instanceof Error ? error.message : 'Failed to create configuration');
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ configId, updates }: { configId: string; updates: UpdateConfigRequest }) =>
      configsApi.update(configId, updates),
    onSuccess: (updatedConfig) => {
      updateConfiguration(updatedConfig.configId, updatedConfig);
      queryClient.invalidateQueries({ queryKey: CONFIGS_QUERY_KEY });
      closeForm();
    },
    onError: (error) => {
      setError(error instanceof Error ? error.message : 'Failed to update configuration');
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (configId: string) => configsApi.delete(configId),
    onMutate: (configId) => {
      // Optimistic update
      markPendingDelete(configId);
    },
    onSuccess: (_, configId) => {
      removeConfiguration(configId);
      unmarkPendingDelete(configId);
      queryClient.invalidateQueries({ queryKey: CONFIGS_QUERY_KEY });
    },
    onError: (error, configId) => {
      unmarkPendingDelete(configId);
      setError(error instanceof Error ? error.message : 'Failed to delete configuration');
    },
  });

  // Actions
  const createConfig = useCallback(
    (config: CreateConfigRequest) => {
      createMutation.mutate(config);
    },
    [createMutation]
  );

  const updateConfig = useCallback(
    (configId: string, updates: UpdateConfigRequest) => {
      updateMutation.mutate({ configId, updates });
    },
    [updateMutation]
  );

  const deleteConfig = useCallback(
    (configId: string) => {
      deleteMutation.mutate(configId);
    },
    [deleteMutation]
  );

  // Get active configuration
  const activeConfig = configurations.find((c) => c.configId === activeConfigId) || null;

  // Filter out pending deletes for display
  const visibleConfigurations = configurations.filter(
    (c) => !pendingDeletes.has(c.configId)
  );

  return {
    // Data
    configurations: visibleConfigurations,
    activeConfig,
    activeConfigId,
    maxAllowed: data?.maxAllowed ?? 3,

    // Loading states
    isLoading: isFetching,
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,

    // Errors
    error: fetchError?.message || null,

    // Form state
    isFormOpen,
    editingConfig,
    deletingConfigId,

    // Actions
    refetch,
    createConfig,
    updateConfig,
    deleteConfig,
    setActiveConfig,
    openCreateForm,
    openEditForm,
    closeForm,
    startDelete,
    cancelDelete,
    confirmDelete,
  };
}

// Hook for getting a single config with its metrics
export function useConfig(configId: string | null) {
  const { configurations } = useConfigStore();

  const config = configId
    ? configurations.find((c) => c.configId === configId) || null
    : null;

  const { data: configDetail, isLoading } = useQuery({
    queryKey: ['configuration', configId],
    queryFn: () => (configId ? configsApi.get(configId) : null),
    enabled: !!configId,
    staleTime: 60 * 1000, // 1 minute
  });

  return {
    config: configDetail || config,
    isLoading,
  };
}
