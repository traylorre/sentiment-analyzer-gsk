'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type ViewType = 'dashboard' | 'configs' | 'alerts' | 'settings';

export interface ViewState {
  // Current active view
  currentView: ViewType;
  previousView: ViewType | null;

  // Navigation state
  isNavigating: boolean;
  navigationDirection: 'left' | 'right' | null;

  // Gesture state
  isGesturing: boolean;
  gestureProgress: number; // 0-1 progress of swipe
  gestureDirection: 'left' | 'right' | null;

  // Bottom sheet state
  isBottomSheetOpen: boolean;
  bottomSheetContent: string | null;

  // Pull to refresh state
  isPulling: boolean;
  pullProgress: number;
  isRefreshing: boolean;

  // Actions
  setView: (view: ViewType) => void;
  navigateLeft: () => void;
  navigateRight: () => void;

  startGesture: (direction: 'left' | 'right') => void;
  updateGesture: (progress: number) => void;
  endGesture: (shouldNavigate: boolean) => void;
  cancelGesture: () => void;

  openBottomSheet: (content: string) => void;
  closeBottomSheet: () => void;

  startPull: () => void;
  updatePull: (progress: number) => void;
  triggerRefresh: () => void;
  endRefresh: () => void;

  reset: () => void;
}

const VIEW_ORDER: ViewType[] = ['dashboard', 'configs', 'alerts', 'settings'];

const getAdjacentView = (current: ViewType, direction: 'left' | 'right'): ViewType | null => {
  const currentIndex = VIEW_ORDER.indexOf(current);
  if (direction === 'left') {
    return currentIndex > 0 ? VIEW_ORDER[currentIndex - 1] : null;
  }
  return currentIndex < VIEW_ORDER.length - 1 ? VIEW_ORDER[currentIndex + 1] : null;
};

const initialState = {
  currentView: 'dashboard' as ViewType,
  previousView: null,
  isNavigating: false,
  navigationDirection: null,
  isGesturing: false,
  gestureProgress: 0,
  gestureDirection: null,
  isBottomSheetOpen: false,
  bottomSheetContent: null,
  isPulling: false,
  pullProgress: 0,
  isRefreshing: false,
};

export const useViewStore = create<ViewState>()(
  persist(
    (set, get) => ({
      ...initialState,

      setView: (view) => {
        const current = get().currentView;
        if (view === current) return;

        const currentIndex = VIEW_ORDER.indexOf(current);
        const newIndex = VIEW_ORDER.indexOf(view);
        const direction = newIndex > currentIndex ? 'right' : 'left';

        set({
          previousView: current,
          currentView: view,
          isNavigating: true,
          navigationDirection: direction,
        });

        // Reset navigation state after animation
        setTimeout(() => {
          set({ isNavigating: false, navigationDirection: null });
        }, 300);
      },

      navigateLeft: () => {
        const { currentView, setView } = get();
        const newView = getAdjacentView(currentView, 'left');
        if (newView) {
          setView(newView);
        }
      },

      navigateRight: () => {
        const { currentView, setView } = get();
        const newView = getAdjacentView(currentView, 'right');
        if (newView) {
          setView(newView);
        }
      },

      startGesture: (direction) =>
        set({
          isGesturing: true,
          gestureDirection: direction,
          gestureProgress: 0,
        }),

      updateGesture: (progress) =>
        set({ gestureProgress: Math.min(1, Math.max(0, progress)) }),

      endGesture: (shouldNavigate) => {
        const { gestureDirection, navigateLeft, navigateRight } = get();

        if (shouldNavigate && gestureDirection) {
          if (gestureDirection === 'left') {
            navigateRight(); // Swiping left goes to next (right) view
          } else {
            navigateLeft(); // Swiping right goes to previous (left) view
          }
        }

        set({
          isGesturing: false,
          gestureProgress: 0,
          gestureDirection: null,
        });
      },

      cancelGesture: () =>
        set({
          isGesturing: false,
          gestureProgress: 0,
          gestureDirection: null,
        }),

      openBottomSheet: (content) =>
        set({
          isBottomSheetOpen: true,
          bottomSheetContent: content,
        }),

      closeBottomSheet: () =>
        set({
          isBottomSheetOpen: false,
          bottomSheetContent: null,
        }),

      startPull: () => set({ isPulling: true, pullProgress: 0 }),

      updatePull: (progress) =>
        set({ pullProgress: Math.min(1, Math.max(0, progress)) }),

      triggerRefresh: () =>
        set({ isPulling: false, pullProgress: 0, isRefreshing: true }),

      endRefresh: () => set({ isRefreshing: false }),

      reset: () => set(initialState),
    }),
    {
      name: 'view-store',
      partialize: (state) => ({ currentView: state.currentView }),
    }
  )
);

// Selector hooks for performance
export const useCurrentView = () => useViewStore((state) => state.currentView);
export const useIsNavigating = () => useViewStore((state) => state.isNavigating);
export const useIsGesturing = () => useViewStore((state) => state.isGesturing);
export const useIsBottomSheetOpen = () => useViewStore((state) => state.isBottomSheetOpen);
export const useIsRefreshing = () => useViewStore((state) => state.isRefreshing);
