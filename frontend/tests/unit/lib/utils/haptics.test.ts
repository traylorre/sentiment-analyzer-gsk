import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  triggerHaptic,
  isHapticSupported,
  haptic,
} from '@/lib/utils/haptics';

describe('Haptics Utilities', () => {
  beforeEach(() => {
    // Reset the mock from setup.ts
    vi.mocked(navigator.vibrate).mockReset();
    vi.mocked(navigator.vibrate).mockReturnValue(true);
  });

  describe('isHapticSupported', () => {
    it('should return true when vibrate is available', () => {
      expect(isHapticSupported()).toBe(true);
    });
  });

  describe('triggerHaptic', () => {
    it('should call vibrate with light pattern (10ms)', () => {
      triggerHaptic('light');
      expect(navigator.vibrate).toHaveBeenCalledWith(10);
    });

    it('should call vibrate with medium pattern (20ms)', () => {
      triggerHaptic('medium');
      expect(navigator.vibrate).toHaveBeenCalledWith(20);
    });

    it('should call vibrate with heavy pattern (30ms)', () => {
      triggerHaptic('heavy');
      expect(navigator.vibrate).toHaveBeenCalledWith(30);
    });

    it('should call vibrate with selection pattern', () => {
      triggerHaptic('selection');
      expect(navigator.vibrate).toHaveBeenCalledWith([5, 10, 5]);
    });

    it('should default to light when no intensity specified', () => {
      triggerHaptic();
      expect(navigator.vibrate).toHaveBeenCalledWith(10);
    });

    it('should return true when vibrate succeeds', () => {
      expect(triggerHaptic('light')).toBe(true);
    });

    it('should return false when vibrate throws', () => {
      vi.mocked(navigator.vibrate).mockImplementation(() => {
        throw new Error('Vibration failed');
      });
      expect(triggerHaptic('light')).toBe(false);
    });
  });

  describe('haptic convenience methods', () => {
    it('should have light method that calls triggerHaptic', () => {
      haptic.light();
      expect(navigator.vibrate).toHaveBeenCalledWith(10);
    });

    it('should have medium method that calls triggerHaptic', () => {
      haptic.medium();
      expect(navigator.vibrate).toHaveBeenCalledWith(20);
    });

    it('should have heavy method that calls triggerHaptic', () => {
      haptic.heavy();
      expect(navigator.vibrate).toHaveBeenCalledWith(30);
    });

    it('should have selection method that calls triggerHaptic', () => {
      haptic.selection();
      expect(navigator.vibrate).toHaveBeenCalledWith([5, 10, 5]);
    });

    it('should have isSupported method', () => {
      expect(haptic.isSupported()).toBe(true);
    });
  });
});
