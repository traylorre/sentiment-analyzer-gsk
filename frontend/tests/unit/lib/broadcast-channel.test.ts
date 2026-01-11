/**
 * Unit tests for AuthBroadcastSync utility.
 *
 * Feature: 1191 - Mid-Session Tier Upgrade
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AuthBroadcastSync, getAuthBroadcastSync } from '@/lib/sync/broadcast-channel';

describe('AuthBroadcastSync', () => {
  let mockBroadcastChannel: {
    postMessage: ReturnType<typeof vi.fn>;
    close: ReturnType<typeof vi.fn>;
    onmessage: ((event: MessageEvent) => void) | null;
  };

  beforeEach(() => {
    // Mock BroadcastChannel
    mockBroadcastChannel = {
      postMessage: vi.fn(),
      close: vi.fn(),
      onmessage: null,
    };

    vi.stubGlobal(
      'BroadcastChannel',
      vi.fn(() => mockBroadcastChannel)
    );

    // Mock crypto.randomUUID
    vi.stubGlobal('crypto', {
      randomUUID: () => 'test-tab-id',
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('connect', () => {
    it('should create BroadcastChannel when available', () => {
      const sync = new AuthBroadcastSync();
      sync.connect();

      expect(BroadcastChannel).toHaveBeenCalledWith('sentiment-analyzer-auth');
    });

    it('should set up message handler', () => {
      const sync = new AuthBroadcastSync();
      sync.connect();

      expect(mockBroadcastChannel.onmessage).toBeDefined();
    });
  });

  describe('disconnect', () => {
    it('should close the channel', () => {
      const sync = new AuthBroadcastSync();
      sync.connect();
      sync.disconnect();

      expect(mockBroadcastChannel.close).toHaveBeenCalled();
    });

    it('should clear listeners', () => {
      const sync = new AuthBroadcastSync();
      const handler = vi.fn();

      sync.connect();
      sync.on('ROLE_UPGRADED', handler);
      sync.disconnect();

      // Simulate message after disconnect - handler should not be called
      // (listeners cleared)
    });
  });

  describe('broadcast', () => {
    it('should post message with correct format', () => {
      const sync = new AuthBroadcastSync();
      sync.connect();

      sync.broadcast('ROLE_UPGRADED', { userId: 'user_123', newRole: 'paid' });

      expect(mockBroadcastChannel.postMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'AUTH',
          version: 1,
          sourceTabId: 'test-tab-id',
          data: {
            action: 'ROLE_UPGRADED',
            userId: 'user_123',
            newRole: 'paid',
          },
        })
      );
    });

    it('should include timestamp', () => {
      const sync = new AuthBroadcastSync();
      sync.connect();

      const before = Date.now();
      sync.broadcast('SIGN_OUT');
      const after = Date.now();

      const call = mockBroadcastChannel.postMessage.mock.calls[0][0];
      expect(call.timestamp).toBeGreaterThanOrEqual(before);
      expect(call.timestamp).toBeLessThanOrEqual(after);
    });
  });

  describe('on/off', () => {
    it('should register and call handlers', () => {
      const sync = new AuthBroadcastSync();
      const handler = vi.fn();

      sync.connect();
      sync.on('ROLE_UPGRADED', handler);

      // Simulate incoming message
      const message = {
        type: 'AUTH',
        version: 1,
        timestamp: Date.now(),
        sourceTabId: 'other-tab-id', // Different tab
        data: {
          action: 'ROLE_UPGRADED',
          userId: 'user_123',
          newRole: 'paid',
        },
      };

      mockBroadcastChannel.onmessage?.({ data: message } as MessageEvent);

      expect(handler).toHaveBeenCalledWith(message.data);
    });

    it('should ignore messages from same tab', () => {
      const sync = new AuthBroadcastSync();
      const handler = vi.fn();

      sync.connect();
      sync.on('ROLE_UPGRADED', handler);

      // Simulate message from same tab
      const message = {
        type: 'AUTH',
        version: 1,
        timestamp: Date.now(),
        sourceTabId: 'test-tab-id', // Same tab ID
        data: {
          action: 'ROLE_UPGRADED',
        },
      };

      mockBroadcastChannel.onmessage?.({ data: message } as MessageEvent);

      expect(handler).not.toHaveBeenCalled();
    });

    it('should unregister handlers with off', () => {
      const sync = new AuthBroadcastSync();
      const handler = vi.fn();

      sync.connect();
      sync.on('ROLE_UPGRADED', handler);
      sync.off('ROLE_UPGRADED', handler);

      const message = {
        type: 'AUTH',
        version: 1,
        timestamp: Date.now(),
        sourceTabId: 'other-tab-id',
        data: {
          action: 'ROLE_UPGRADED',
        },
      };

      mockBroadcastChannel.onmessage?.({ data: message } as MessageEvent);

      expect(handler).not.toHaveBeenCalled();
    });
  });

  describe('message filtering', () => {
    it('should ignore messages with wrong type', () => {
      const sync = new AuthBroadcastSync();
      const handler = vi.fn();

      sync.connect();
      sync.on('ROLE_UPGRADED', handler);

      const message = {
        type: 'INVALID',
        version: 1,
        timestamp: Date.now(),
        sourceTabId: 'other-tab-id',
        data: {
          action: 'ROLE_UPGRADED',
        },
      };

      mockBroadcastChannel.onmessage?.({ data: message } as MessageEvent);

      expect(handler).not.toHaveBeenCalled();
    });

    it('should ignore messages with wrong version', () => {
      const sync = new AuthBroadcastSync();
      const handler = vi.fn();

      sync.connect();
      sync.on('ROLE_UPGRADED', handler);

      const message = {
        type: 'AUTH',
        version: 2, // Wrong version
        timestamp: Date.now(),
        sourceTabId: 'other-tab-id',
        data: {
          action: 'ROLE_UPGRADED',
        },
      };

      mockBroadcastChannel.onmessage?.({ data: message } as MessageEvent);

      expect(handler).not.toHaveBeenCalled();
    });
  });
});

describe('getAuthBroadcastSync', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'BroadcastChannel',
      vi.fn(() => ({
        postMessage: vi.fn(),
        close: vi.fn(),
        onmessage: null,
      }))
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('should return singleton instance', () => {
    const instance1 = getAuthBroadcastSync();
    const instance2 = getAuthBroadcastSync();

    expect(instance1).toBe(instance2);
  });
});
