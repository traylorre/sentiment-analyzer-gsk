import { describe, it, expect, beforeEach } from 'vitest';
import { useAnimationStore } from '@/stores/animation-store';

describe('Animation Store', () => {
  beforeEach(() => {
    // Reset store state before each test
    useAnimationStore.setState({
      pendingAnimations: [],
      activeAnimations: [],
      reducedMotion: false,
      hapticEnabled: true,
    });
  });

  describe('queueAnimation', () => {
    it('should add animation to the queue', () => {
      const { queueAnimation } = useAnimationStore.getState();

      const id = queueAnimation({
        type: 'entrance',
        target: 'test-component',
        priority: 'medium',
        duration: 300,
        delay: 0,
      });

      expect(id).toBeTruthy();
      expect(useAnimationStore.getState().pendingAnimations).toHaveLength(1);
      expect(useAnimationStore.getState().pendingAnimations[0].target).toBe('test-component');
    });

    it('should sort animations by priority', () => {
      const { queueAnimation } = useAnimationStore.getState();

      queueAnimation({
        type: 'entrance',
        target: 'low-priority',
        priority: 'low',
        duration: 300,
        delay: 0,
      });

      queueAnimation({
        type: 'entrance',
        target: 'high-priority',
        priority: 'high',
        duration: 300,
        delay: 0,
      });

      queueAnimation({
        type: 'entrance',
        target: 'medium-priority',
        priority: 'medium',
        duration: 300,
        delay: 0,
      });

      const { pendingAnimations } = useAnimationStore.getState();
      expect(pendingAnimations[0].target).toBe('high-priority');
      expect(pendingAnimations[1].target).toBe('medium-priority');
      expect(pendingAnimations[2].target).toBe('low-priority');
    });
  });

  describe('startAnimation', () => {
    it('should move animation from pending to active', () => {
      const { queueAnimation, startAnimation } = useAnimationStore.getState();

      const id = queueAnimation({
        type: 'entrance',
        target: 'test',
        priority: 'medium',
        duration: 300,
        delay: 0,
      });

      startAnimation(id);

      const state = useAnimationStore.getState();
      expect(state.pendingAnimations).toHaveLength(0);
      expect(state.activeAnimations).toContain(id);
    });
  });

  describe('completeAnimation', () => {
    it('should remove animation from active list', () => {
      const { queueAnimation, startAnimation, completeAnimation } = useAnimationStore.getState();

      const id = queueAnimation({
        type: 'entrance',
        target: 'test',
        priority: 'medium',
        duration: 300,
        delay: 0,
      });

      startAnimation(id);
      completeAnimation(id);

      const state = useAnimationStore.getState();
      expect(state.activeAnimations).not.toContain(id);
    });
  });

  describe('cancelAnimation', () => {
    it('should remove animation from pending queue', () => {
      const { queueAnimation, cancelAnimation } = useAnimationStore.getState();

      const id = queueAnimation({
        type: 'entrance',
        target: 'test',
        priority: 'medium',
        duration: 300,
        delay: 0,
      });

      cancelAnimation(id);

      const state = useAnimationStore.getState();
      expect(state.pendingAnimations).toHaveLength(0);
    });

    it('should remove animation from active list', () => {
      const { queueAnimation, startAnimation, cancelAnimation } = useAnimationStore.getState();

      const id = queueAnimation({
        type: 'entrance',
        target: 'test',
        priority: 'medium',
        duration: 300,
        delay: 0,
      });

      startAnimation(id);
      cancelAnimation(id);

      const state = useAnimationStore.getState();
      expect(state.activeAnimations).not.toContain(id);
    });
  });

  describe('setReducedMotion', () => {
    it('should update reducedMotion state', () => {
      const { setReducedMotion } = useAnimationStore.getState();

      setReducedMotion(true);

      expect(useAnimationStore.getState().reducedMotion).toBe(true);
    });

    it('should clear pending animations when enabled', () => {
      const { queueAnimation, setReducedMotion } = useAnimationStore.getState();

      queueAnimation({
        type: 'entrance',
        target: 'test',
        priority: 'medium',
        duration: 300,
        delay: 0,
      });

      setReducedMotion(true);

      expect(useAnimationStore.getState().pendingAnimations).toHaveLength(0);
    });
  });

  describe('setHapticEnabled', () => {
    it('should update hapticEnabled state', () => {
      const { setHapticEnabled } = useAnimationStore.getState();

      setHapticEnabled(false);

      expect(useAnimationStore.getState().hapticEnabled).toBe(false);
    });
  });
});
