import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type AnimationPriority = 'high' | 'medium' | 'low';
export type AnimationType = 'entrance' | 'exit' | 'update' | 'celebration';

export interface PendingAnimation {
  id: string;
  type: AnimationType;
  target: string;           // Component identifier
  priority: AnimationPriority;
  duration: number;         // milliseconds
  delay: number;
}

interface AnimationState {
  // Queue
  pendingAnimations: PendingAnimation[];
  activeAnimations: string[];   // Animation IDs currently running

  // Preferences
  reducedMotion: boolean;
  hapticEnabled: boolean;

  // Actions
  queueAnimation: (animation: Omit<PendingAnimation, 'id'>) => string;
  startAnimation: (id: string) => void;
  completeAnimation: (id: string) => void;
  cancelAnimation: (id: string) => void;
  clearQueue: () => void;
  setReducedMotion: (enabled: boolean) => void;
  setHapticEnabled: (enabled: boolean) => void;
}

let animationIdCounter = 0;

function generateId(): string {
  return `anim_${++animationIdCounter}_${Date.now()}`;
}

export const useAnimationStore = create<AnimationState>()(
  persist(
    (set, get) => ({
      pendingAnimations: [],
      activeAnimations: [],
      reducedMotion: false,
      hapticEnabled: true,

      queueAnimation: (animation) => {
        const id = generateId();
        const newAnimation: PendingAnimation = { ...animation, id };

        set((state) => {
          // Insert based on priority (high first)
          const priorityOrder = { high: 0, medium: 1, low: 2 };
          const newQueue = [...state.pendingAnimations, newAnimation].sort(
            (a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]
          );
          return { pendingAnimations: newQueue };
        });

        return id;
      },

      startAnimation: (id) => {
        set((state) => ({
          pendingAnimations: state.pendingAnimations.filter((a) => a.id !== id),
          activeAnimations: [...state.activeAnimations, id],
        }));
      },

      completeAnimation: (id) => {
        set((state) => ({
          activeAnimations: state.activeAnimations.filter((aid) => aid !== id),
        }));
      },

      cancelAnimation: (id) => {
        set((state) => ({
          pendingAnimations: state.pendingAnimations.filter((a) => a.id !== id),
          activeAnimations: state.activeAnimations.filter((aid) => aid !== id),
        }));
      },

      clearQueue: () => {
        set({ pendingAnimations: [] });
      },

      setReducedMotion: (enabled) => {
        set({ reducedMotion: enabled });
        if (enabled) {
          // Clear all pending animations when reduced motion is enabled
          set({ pendingAnimations: [] });
        }
      },

      setHapticEnabled: (enabled) => {
        set({ hapticEnabled: enabled });
      },
    }),
    {
      name: 'animation-preferences',
      // Only persist preferences, not animation queue state
      partialize: (state) => ({
        reducedMotion: state.reducedMotion,
        hapticEnabled: state.hapticEnabled,
      }),
    }
  )
);
