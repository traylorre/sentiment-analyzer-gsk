'use client';

import { useCallback, useEffect, useRef } from 'react';
import { useAnimationStore, type AnimationType, type AnimationPriority } from '@/stores/animation-store';
import { useReducedMotion } from './use-reduced-motion';

interface AnimationOptions {
  type?: AnimationType;
  priority?: AnimationPriority;
  duration?: number;
  delay?: number;
}

interface UseAnimationReturn {
  isAnimating: boolean;
  queueEntrance: (target: string, options?: Omit<AnimationOptions, 'type'>) => string;
  queueUpdate: (target: string, options?: Omit<AnimationOptions, 'type'>) => string;
  queueExit: (target: string, options?: Omit<AnimationOptions, 'type'>) => string;
  queueCelebration: (target: string, options?: Omit<AnimationOptions, 'type'>) => string;
  startAnimation: (id: string) => void;
  completeAnimation: (id: string) => void;
  cancelAnimation: (id: string) => void;
  reducedMotion: boolean;
}

const DEFAULT_DURATIONS: Record<AnimationType, number> = {
  entrance: 300,
  exit: 200,
  update: 150,
  celebration: 500,
};

export function useAnimation(): UseAnimationReturn {
  const prefersReducedMotion = useReducedMotion();
  const {
    activeAnimations,
    queueAnimation,
    startAnimation,
    completeAnimation,
    cancelAnimation,
    setReducedMotion,
  } = useAnimationStore();

  // Sync reduced motion preference
  useEffect(() => {
    setReducedMotion(prefersReducedMotion);
  }, [prefersReducedMotion, setReducedMotion]);

  const createQueueFn = useCallback(
    (type: AnimationType) =>
      (target: string, options: Omit<AnimationOptions, 'type'> = {}) => {
        if (prefersReducedMotion) {
          return ''; // No animation queued
        }

        return queueAnimation({
          type,
          target,
          priority: options.priority || 'medium',
          duration: options.duration || DEFAULT_DURATIONS[type],
          delay: options.delay || 0,
        });
      },
    [prefersReducedMotion, queueAnimation]
  );

  return {
    isAnimating: activeAnimations.length > 0,
    queueEntrance: createQueueFn('entrance'),
    queueUpdate: createQueueFn('update'),
    queueExit: createQueueFn('exit'),
    queueCelebration: createQueueFn('celebration'),
    startAnimation,
    completeAnimation,
    cancelAnimation,
    reducedMotion: prefersReducedMotion,
  };
}

/**
 * Hook for tracking a specific animation target
 */
export function useAnimationTarget(target: string) {
  const { activeAnimations, pendingAnimations } = useAnimationStore();
  const animationIdRef = useRef<string | null>(null);

  const isPending = pendingAnimations.some((a) => a.target === target);
  const isActive = activeAnimations.some((id) => id === animationIdRef.current);

  return {
    isPending,
    isActive,
    setAnimationId: (id: string) => {
      animationIdRef.current = id;
    },
  };
}
