'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { Configuration, CreateConfigRequest, UpdateConfigRequest } from '@/types/config';

interface ConfigState {
  // Current state
  configurations: Configuration[];
  activeConfigId: string | null;
  isLoading: boolean;
  error: string | null;

  // UI state
  isFormOpen: boolean;
  editingConfig: Configuration | null;
  deletingConfigId: string | null;

  // Optimistic updates queue
  pendingDeletes: Set<string>;
}

interface ConfigActions {
  // CRUD operations
  setConfigurations: (configs: Configuration[]) => void;
  addConfiguration: (config: Configuration) => void;
  updateConfiguration: (configId: string, updates: Partial<Configuration>) => void;
  removeConfiguration: (configId: string) => void;

  // Active config
  setActiveConfig: (configId: string | null) => void;

  // UI actions
  openCreateForm: () => void;
  openEditForm: (config: Configuration) => void;
  closeForm: () => void;
  startDelete: (configId: string) => void;
  cancelDelete: () => void;
  confirmDelete: () => void;

  // State
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;

  // Optimistic updates
  markPendingDelete: (configId: string) => void;
  unmarkPendingDelete: (configId: string) => void;

  // Reset
  reset: () => void;
}

type ConfigStore = ConfigState & ConfigActions;

const initialState: ConfigState = {
  configurations: [],
  activeConfigId: null,
  isLoading: false,
  error: null,
  isFormOpen: false,
  editingConfig: null,
  deletingConfigId: null,
  pendingDeletes: new Set(),
};

export const useConfigStore = create<ConfigStore>()(
  persist(
    (set, get) => ({
      ...initialState,

      // CRUD operations
      setConfigurations: (configs) => set({ configurations: configs }),

      addConfiguration: (config) =>
        set((state) => ({
          configurations: [...state.configurations, config],
        })),

      updateConfiguration: (configId, updates) =>
        set((state) => ({
          configurations: state.configurations.map((c) =>
            c.configId === configId ? { ...c, ...updates } : c
          ),
        })),

      removeConfiguration: (configId) =>
        set((state) => ({
          configurations: state.configurations.filter(
            (c) => c.configId !== configId
          ),
          activeConfigId:
            state.activeConfigId === configId ? null : state.activeConfigId,
        })),

      // Active config
      setActiveConfig: (configId) => set({ activeConfigId: configId }),

      // UI actions
      openCreateForm: () =>
        set({
          isFormOpen: true,
          editingConfig: null,
        }),

      openEditForm: (config) =>
        set({
          isFormOpen: true,
          editingConfig: config,
        }),

      closeForm: () =>
        set({
          isFormOpen: false,
          editingConfig: null,
        }),

      startDelete: (configId) => set({ deletingConfigId: configId }),

      cancelDelete: () => set({ deletingConfigId: null }),

      confirmDelete: () => {
        const { deletingConfigId, removeConfiguration } = get();
        if (deletingConfigId) {
          removeConfiguration(deletingConfigId);
          set({ deletingConfigId: null });
        }
      },

      // State
      setLoading: (loading) => set({ isLoading: loading }),
      setError: (error) => set({ error }),

      // Optimistic updates
      markPendingDelete: (configId) =>
        set((state) => ({
          pendingDeletes: new Set([...Array.from(state.pendingDeletes), configId]),
        })),

      unmarkPendingDelete: (configId) =>
        set((state) => {
          const newSet = new Set(state.pendingDeletes);
          newSet.delete(configId);
          return { pendingDeletes: newSet };
        }),

      // Reset
      reset: () => set(initialState),
    }),
    {
      name: 'sentiment-configs',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        activeConfigId: state.activeConfigId,
      }),
    }
  )
);

// Selector hooks
export const useActiveConfig = () => {
  const { configurations, activeConfigId } = useConfigStore();
  return configurations.find((c) => c.configId === activeConfigId) || null;
};

export const useConfigById = (configId: string | null) => {
  const { configurations } = useConfigStore();
  if (!configId) return null;
  return configurations.find((c) => c.configId === configId) || null;
};

export const useConfigCount = () => {
  const { configurations } = useConfigStore();
  return configurations.length;
};

export const useIsMaxConfigs = (maxAllowed: number = 3) => {
  const count = useConfigCount();
  return count >= maxAllowed;
};
