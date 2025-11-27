import { describe, it, expect, beforeEach } from 'vitest';
import { useConfigStore } from '@/stores/config-store';
import type { Configuration } from '@/types/config';

const mockConfig: Configuration = {
  configId: 'config-1',
  name: 'Tech Watchlist',
  tickers: [
    { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
    { symbol: 'GOOGL', name: 'Alphabet Inc.', exchange: 'NASDAQ' },
  ],
  timeframeDays: 7,
  includeExtendedHours: false,
  createdAt: '2024-01-15T10:00:00Z',
  updatedAt: '2024-01-15T10:00:00Z',
};

const mockConfig2: Configuration = {
  configId: 'config-2',
  name: 'Finance Sector',
  tickers: [
    { symbol: 'JPM', name: 'JPMorgan Chase', exchange: 'NYSE' },
  ],
  timeframeDays: 14,
  includeExtendedHours: true,
  createdAt: '2024-01-16T10:00:00Z',
  updatedAt: '2024-01-16T10:00:00Z',
};

describe('Config Store', () => {
  beforeEach(() => {
    useConfigStore.getState().reset();
  });

  describe('initial state', () => {
    it('should have correct initial values', () => {
      const state = useConfigStore.getState();

      expect(state.configurations).toEqual([]);
      expect(state.activeConfigId).toBeNull();
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
      expect(state.isFormOpen).toBe(false);
      expect(state.editingConfig).toBeNull();
      expect(state.deletingConfigId).toBeNull();
      expect(state.pendingDeletes.size).toBe(0);
    });
  });

  describe('CRUD operations', () => {
    describe('setConfigurations', () => {
      it('should replace all configurations', () => {
        const { setConfigurations } = useConfigStore.getState();

        setConfigurations([mockConfig, mockConfig2]);

        const state = useConfigStore.getState();
        expect(state.configurations).toHaveLength(2);
        expect(state.configurations[0].configId).toBe('config-1');
        expect(state.configurations[1].configId).toBe('config-2');
      });
    });

    describe('addConfiguration', () => {
      it('should add a new configuration', () => {
        const { addConfiguration } = useConfigStore.getState();

        addConfiguration(mockConfig);

        expect(useConfigStore.getState().configurations).toHaveLength(1);
        expect(useConfigStore.getState().configurations[0]).toEqual(mockConfig);
      });

      it('should append to existing configurations', () => {
        const { setConfigurations, addConfiguration } = useConfigStore.getState();

        setConfigurations([mockConfig]);
        addConfiguration(mockConfig2);

        expect(useConfigStore.getState().configurations).toHaveLength(2);
      });
    });

    describe('updateConfiguration', () => {
      it('should update an existing configuration', () => {
        const { setConfigurations, updateConfiguration } = useConfigStore.getState();

        setConfigurations([mockConfig]);
        updateConfiguration('config-1', { name: 'Updated Name', timeframeDays: 30 });

        const updated = useConfigStore.getState().configurations[0];
        expect(updated.name).toBe('Updated Name');
        expect(updated.timeframeDays).toBe(30);
        expect(updated.tickers).toEqual(mockConfig.tickers);
      });

      it('should not update non-existent configuration', () => {
        const { setConfigurations, updateConfiguration } = useConfigStore.getState();

        setConfigurations([mockConfig]);
        updateConfiguration('non-existent', { name: 'Updated' });

        expect(useConfigStore.getState().configurations[0].name).toBe('Tech Watchlist');
      });
    });

    describe('removeConfiguration', () => {
      it('should remove a configuration', () => {
        const { setConfigurations, removeConfiguration } = useConfigStore.getState();

        setConfigurations([mockConfig, mockConfig2]);
        removeConfiguration('config-1');

        expect(useConfigStore.getState().configurations).toHaveLength(1);
        expect(useConfigStore.getState().configurations[0].configId).toBe('config-2');
      });

      it('should clear activeConfigId if removing active config', () => {
        const { setConfigurations, setActiveConfig, removeConfiguration } = useConfigStore.getState();

        setConfigurations([mockConfig, mockConfig2]);
        setActiveConfig('config-1');
        removeConfiguration('config-1');

        expect(useConfigStore.getState().activeConfigId).toBeNull();
      });

      it('should not clear activeConfigId if removing different config', () => {
        const { setConfigurations, setActiveConfig, removeConfiguration } = useConfigStore.getState();

        setConfigurations([mockConfig, mockConfig2]);
        setActiveConfig('config-1');
        removeConfiguration('config-2');

        expect(useConfigStore.getState().activeConfigId).toBe('config-1');
      });
    });
  });

  describe('active config', () => {
    it('should set active config', () => {
      const { setActiveConfig } = useConfigStore.getState();

      setActiveConfig('config-1');

      expect(useConfigStore.getState().activeConfigId).toBe('config-1');
    });

    it('should clear active config', () => {
      const { setActiveConfig } = useConfigStore.getState();

      setActiveConfig('config-1');
      setActiveConfig(null);

      expect(useConfigStore.getState().activeConfigId).toBeNull();
    });
  });

  describe('UI actions', () => {
    describe('form actions', () => {
      it('should open create form', () => {
        const { openCreateForm } = useConfigStore.getState();

        openCreateForm();

        const state = useConfigStore.getState();
        expect(state.isFormOpen).toBe(true);
        expect(state.editingConfig).toBeNull();
      });

      it('should open edit form with config', () => {
        const { openEditForm } = useConfigStore.getState();

        openEditForm(mockConfig);

        const state = useConfigStore.getState();
        expect(state.isFormOpen).toBe(true);
        expect(state.editingConfig).toEqual(mockConfig);
      });

      it('should close form and clear editing state', () => {
        const { openEditForm, closeForm } = useConfigStore.getState();

        openEditForm(mockConfig);
        closeForm();

        const state = useConfigStore.getState();
        expect(state.isFormOpen).toBe(false);
        expect(state.editingConfig).toBeNull();
      });
    });

    describe('delete actions', () => {
      it('should start delete process', () => {
        const { startDelete } = useConfigStore.getState();

        startDelete('config-1');

        expect(useConfigStore.getState().deletingConfigId).toBe('config-1');
      });

      it('should cancel delete process', () => {
        const { startDelete, cancelDelete } = useConfigStore.getState();

        startDelete('config-1');
        cancelDelete();

        expect(useConfigStore.getState().deletingConfigId).toBeNull();
      });

      it('should confirm delete and remove config', () => {
        const { setConfigurations, startDelete, confirmDelete } = useConfigStore.getState();

        setConfigurations([mockConfig, mockConfig2]);
        startDelete('config-1');
        confirmDelete();

        const state = useConfigStore.getState();
        expect(state.deletingConfigId).toBeNull();
        expect(state.configurations).toHaveLength(1);
        expect(state.configurations[0].configId).toBe('config-2');
      });
    });
  });

  describe('state setters', () => {
    it('should set loading state', () => {
      const { setLoading } = useConfigStore.getState();

      setLoading(true);
      expect(useConfigStore.getState().isLoading).toBe(true);

      setLoading(false);
      expect(useConfigStore.getState().isLoading).toBe(false);
    });

    it('should set error state', () => {
      const { setError } = useConfigStore.getState();

      setError('Something went wrong');
      expect(useConfigStore.getState().error).toBe('Something went wrong');

      setError(null);
      expect(useConfigStore.getState().error).toBeNull();
    });
  });

  describe('optimistic updates', () => {
    it('should mark config as pending delete', () => {
      const { markPendingDelete } = useConfigStore.getState();

      markPendingDelete('config-1');

      expect(useConfigStore.getState().pendingDeletes.has('config-1')).toBe(true);
    });

    it('should unmark config from pending delete', () => {
      const { markPendingDelete, unmarkPendingDelete } = useConfigStore.getState();

      markPendingDelete('config-1');
      markPendingDelete('config-2');
      unmarkPendingDelete('config-1');

      const state = useConfigStore.getState();
      expect(state.pendingDeletes.has('config-1')).toBe(false);
      expect(state.pendingDeletes.has('config-2')).toBe(true);
    });
  });

  describe('reset', () => {
    it('should reset all state to initial values', () => {
      const store = useConfigStore.getState();

      // Set up various state
      store.setConfigurations([mockConfig]);
      store.setActiveConfig('config-1');
      store.openEditForm(mockConfig);
      store.setError('Test error');
      store.markPendingDelete('config-1');

      store.reset();

      const state = useConfigStore.getState();
      expect(state.configurations).toEqual([]);
      expect(state.activeConfigId).toBeNull();
      expect(state.isFormOpen).toBe(false);
      expect(state.editingConfig).toBeNull();
      expect(state.error).toBeNull();
      expect(state.pendingDeletes.size).toBe(0);
    });
  });
});
