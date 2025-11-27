import { describe, it, expect, beforeEach } from 'vitest';
import { useViewStore } from '@/stores/view-store';

describe('View Store', () => {
  beforeEach(() => {
    // Reset store state before each test
    useViewStore.getState().reset();
  });

  describe('setView', () => {
    it('should update currentView', () => {
      const { setView } = useViewStore.getState();

      setView('configs');

      expect(useViewStore.getState().currentView).toBe('configs');
    });

    it('should set previousView when changing views', () => {
      const { setView } = useViewStore.getState();

      setView('configs');

      expect(useViewStore.getState().previousView).toBe('dashboard');
    });

    it('should not change if same view', () => {
      const store = useViewStore.getState();
      const initialPreviousView = store.previousView;

      store.setView('dashboard'); // Already on dashboard

      expect(useViewStore.getState().previousView).toBe(initialPreviousView);
    });

    it('should set navigation direction to right when going forward', () => {
      const { setView } = useViewStore.getState();

      setView('configs');

      expect(useViewStore.getState().navigationDirection).toBe('right');
    });

    it('should set navigation direction to left when going backward', () => {
      const { setView } = useViewStore.getState();

      setView('alerts'); // Go forward
      setView('dashboard'); // Go backward

      expect(useViewStore.getState().navigationDirection).toBe('left');
    });
  });

  describe('navigateLeft', () => {
    it('should not navigate left from dashboard (first view)', () => {
      const { navigateLeft } = useViewStore.getState();

      navigateLeft();

      expect(useViewStore.getState().currentView).toBe('dashboard');
    });

    it('should navigate to previous view', () => {
      const { setView, navigateLeft } = useViewStore.getState();

      setView('configs');
      navigateLeft();

      expect(useViewStore.getState().currentView).toBe('dashboard');
    });
  });

  describe('navigateRight', () => {
    it('should navigate to next view', () => {
      const { navigateRight } = useViewStore.getState();

      navigateRight();

      expect(useViewStore.getState().currentView).toBe('configs');
    });

    it('should not navigate right from settings (last view)', () => {
      const { setView, navigateRight } = useViewStore.getState();

      setView('settings');
      navigateRight();

      expect(useViewStore.getState().currentView).toBe('settings');
    });
  });

  describe('gesture state', () => {
    it('should start gesture with direction', () => {
      const { startGesture } = useViewStore.getState();

      startGesture('left');

      const state = useViewStore.getState();
      expect(state.isGesturing).toBe(true);
      expect(state.gestureDirection).toBe('left');
      expect(state.gestureProgress).toBe(0);
    });

    it('should update gesture progress', () => {
      const { startGesture, updateGesture } = useViewStore.getState();

      startGesture('left');
      updateGesture(0.5);

      expect(useViewStore.getState().gestureProgress).toBe(0.5);
    });

    it('should clamp gesture progress between 0 and 1', () => {
      const { startGesture, updateGesture } = useViewStore.getState();

      startGesture('left');
      updateGesture(1.5);

      expect(useViewStore.getState().gestureProgress).toBe(1);

      updateGesture(-0.5);

      expect(useViewStore.getState().gestureProgress).toBe(0);
    });

    it('should end gesture and reset state', () => {
      const { startGesture, updateGesture, endGesture } = useViewStore.getState();

      startGesture('left');
      updateGesture(0.5);
      endGesture(false);

      const state = useViewStore.getState();
      expect(state.isGesturing).toBe(false);
      expect(state.gestureProgress).toBe(0);
      expect(state.gestureDirection).toBeNull();
    });

    it('should navigate when endGesture is called with shouldNavigate=true', () => {
      const { startGesture, updateGesture, endGesture } = useViewStore.getState();

      startGesture('left'); // Swiping left goes to next view
      updateGesture(1);
      endGesture(true);

      expect(useViewStore.getState().currentView).toBe('configs');
    });

    it('should cancel gesture and reset state', () => {
      const { startGesture, updateGesture, cancelGesture } = useViewStore.getState();

      startGesture('right');
      updateGesture(0.7);
      cancelGesture();

      const state = useViewStore.getState();
      expect(state.isGesturing).toBe(false);
      expect(state.gestureProgress).toBe(0);
      expect(state.gestureDirection).toBeNull();
    });
  });

  describe('bottom sheet', () => {
    it('should open bottom sheet with content', () => {
      const { openBottomSheet } = useViewStore.getState();

      openBottomSheet('test-content');

      const state = useViewStore.getState();
      expect(state.isBottomSheetOpen).toBe(true);
      expect(state.bottomSheetContent).toBe('test-content');
    });

    it('should close bottom sheet', () => {
      const { openBottomSheet, closeBottomSheet } = useViewStore.getState();

      openBottomSheet('test-content');
      closeBottomSheet();

      const state = useViewStore.getState();
      expect(state.isBottomSheetOpen).toBe(false);
      expect(state.bottomSheetContent).toBeNull();
    });
  });

  describe('pull to refresh', () => {
    it('should start pull', () => {
      const { startPull } = useViewStore.getState();

      startPull();

      const state = useViewStore.getState();
      expect(state.isPulling).toBe(true);
      expect(state.pullProgress).toBe(0);
    });

    it('should update pull progress', () => {
      const { startPull, updatePull } = useViewStore.getState();

      startPull();
      updatePull(0.6);

      expect(useViewStore.getState().pullProgress).toBe(0.6);
    });

    it('should clamp pull progress between 0 and 1', () => {
      const { startPull, updatePull } = useViewStore.getState();

      startPull();
      updatePull(1.5);

      expect(useViewStore.getState().pullProgress).toBe(1);
    });

    it('should trigger refresh', () => {
      const { startPull, updatePull, triggerRefresh } = useViewStore.getState();

      startPull();
      updatePull(1);
      triggerRefresh();

      const state = useViewStore.getState();
      expect(state.isPulling).toBe(false);
      expect(state.pullProgress).toBe(0);
      expect(state.isRefreshing).toBe(true);
    });

    it('should end refresh', () => {
      const { triggerRefresh, endRefresh } = useViewStore.getState();

      triggerRefresh();
      endRefresh();

      expect(useViewStore.getState().isRefreshing).toBe(false);
    });
  });

  describe('reset', () => {
    it('should reset all state to initial values', () => {
      const store = useViewStore.getState();

      store.setView('alerts');
      store.startGesture('left');
      store.updateGesture(0.5);
      store.openBottomSheet('content');
      store.startPull();
      store.updatePull(0.7);

      store.reset();

      const state = useViewStore.getState();
      expect(state.currentView).toBe('dashboard');
      expect(state.previousView).toBeNull();
      expect(state.isGesturing).toBe(false);
      expect(state.isBottomSheetOpen).toBe(false);
      expect(state.isPulling).toBe(false);
    });
  });
});
