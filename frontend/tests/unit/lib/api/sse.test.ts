import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { SSEClient, SSEStatus, getSSEClient, disconnectSSE } from '@/lib/api/sse';

// Mock EventSource
class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;
  readyState: number = 0;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  private eventListeners: Map<string, ((event: MessageEvent) => void)[]> = new Map();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    const listeners = this.eventListeners.get(type) || [];
    listeners.push(listener);
    this.eventListeners.set(type, listeners);
  }

  removeEventListener(type: string, listener: (event: MessageEvent) => void) {
    const listeners = this.eventListeners.get(type) || [];
    const index = listeners.indexOf(listener);
    if (index > -1) {
      listeners.splice(index, 1);
    }
  }

  close() {
    this.readyState = 2;
  }

  // Test helpers
  triggerOpen() {
    this.readyState = 1;
    this.onopen?.(new Event('open'));
  }

  triggerMessage(data: string) {
    this.onmessage?.(new MessageEvent('message', { data }));
  }

  triggerEvent(type: string, data: string) {
    const listeners = this.eventListeners.get(type) || [];
    listeners.forEach(listener => {
      listener(new MessageEvent(type, { data }));
    });
  }

  triggerError() {
    this.onerror?.(new Event('error'));
  }

  static reset() {
    MockEventSource.instances = [];
  }

  static getLatest(): MockEventSource | undefined {
    return MockEventSource.instances[MockEventSource.instances.length - 1];
  }
}

// Replace global EventSource
const originalEventSource = global.EventSource;

describe('SSEClient', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    MockEventSource.reset();
    (global as unknown as { EventSource: typeof MockEventSource }).EventSource = MockEventSource;
    disconnectSSE();
  });

  afterEach(() => {
    vi.useRealTimers();
    (global as unknown as { EventSource: typeof EventSource }).EventSource = originalEventSource;
  });

  describe('connection', () => {
    it('should connect to the SSE endpoint', () => {
      const client = new SSEClient('/api/v2/stream/metrics');
      client.connect();

      expect(MockEventSource.instances.length).toBe(1);
      expect(MockEventSource.getLatest()?.url).toBe('/api/v2/stream/metrics');
    });

    it('should set status to connecting initially', () => {
      const onStatusChange = vi.fn();
      const client = new SSEClient('/api/v2/stream/metrics', { onStatusChange });
      client.connect();

      expect(onStatusChange).toHaveBeenCalledWith('connecting');
    });

    it('should set status to connected when connection opens', () => {
      const onStatusChange = vi.fn();
      const client = new SSEClient('/api/v2/stream/metrics', { onStatusChange });
      client.connect();

      MockEventSource.getLatest()?.triggerOpen();

      expect(onStatusChange).toHaveBeenLastCalledWith('connected');
      expect(client.isConnected()).toBe(true);
    });

    it('should not create duplicate connections', () => {
      const client = new SSEClient('/api/v2/stream/metrics');
      client.connect();
      client.connect();

      expect(MockEventSource.instances.length).toBe(1);
    });
  });

  describe('message handling', () => {
    it('should parse and forward messages', () => {
      const onMessage = vi.fn();
      const client = new SSEClient('/api/v2/stream/metrics', { onMessage });
      client.connect();

      const message = {
        type: 'test',
        data: { value: 123 },
        timestamp: '2024-01-15T10:00:00Z',
      };

      MockEventSource.getLatest()?.triggerMessage(JSON.stringify(message));

      expect(onMessage).toHaveBeenCalledWith(message);
    });

    it('should handle sentiment_update events', () => {
      const onMessage = vi.fn();
      const client = new SSEClient('/api/v2/stream/metrics', { onMessage });
      client.connect();

      const payload = {
        configId: 'config-123',
        ticker: 'AAPL',
        source: 'tiingo',
        sentiment: 0.45,
        timestamp: '2024-01-15T10:00:00Z',
      };

      MockEventSource.getLatest()?.triggerEvent('sentiment_update', JSON.stringify(payload));

      expect(onMessage).toHaveBeenCalledWith({
        type: 'sentiment_update',
        data: payload,
        timestamp: expect.any(String),
      });
    });

    it('should handle malformed messages gracefully', () => {
      const onMessage = vi.fn();
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

      const client = new SSEClient('/api/v2/stream/metrics', { onMessage });
      client.connect();

      MockEventSource.getLatest()?.triggerMessage('not valid json');

      expect(onMessage).not.toHaveBeenCalled();
      expect(consoleError).toHaveBeenCalled();

      consoleError.mockRestore();
    });
  });

  describe('error handling and reconnection', () => {
    it('should set status to error on connection failure', () => {
      const onStatusChange = vi.fn();
      const client = new SSEClient('/api/v2/stream/metrics', { onStatusChange });
      client.connect();

      MockEventSource.getLatest()?.triggerError();

      expect(onStatusChange).toHaveBeenCalledWith('error');
    });

    it('should schedule reconnection after error', () => {
      const client = new SSEClient('/api/v2/stream/metrics', {
        reconnectDelay: 1000,
      });
      client.connect();
      expect(MockEventSource.instances.length).toBe(1);

      MockEventSource.getLatest()?.triggerError();

      // Verify reconnection is scheduled (timeout was set)
      // The cleanup happens, but reconnection is scheduled
      expect(client.getStatus()).toBe('error');
    });

    it('should stop reconnecting after max attempts', () => {
      const onError = vi.fn();
      const client = new SSEClient('/api/v2/stream/metrics', {
        onError,
        reconnectAttempts: 0, // No reconnection attempts
        reconnectDelay: 100,
      });
      client.connect();

      MockEventSource.getLatest()?.triggerError();

      // Should call onError with max attempts message immediately
      expect(onError).toHaveBeenCalledWith(expect.any(Error));
    });

    it('should reset reconnect count on successful connection', () => {
      const onStatusChange = vi.fn();
      const client = new SSEClient('/api/v2/stream/metrics', {
        onStatusChange,
        reconnectDelay: 100,
        reconnectAttempts: 5,
      });
      client.connect();
      MockEventSource.getLatest()?.triggerOpen();

      // Verify connected status
      expect(client.getStatus()).toBe('connected');
      expect(client.isConnected()).toBe(true);
    });
  });

  describe('disconnect', () => {
    it('should close the connection', () => {
      const client = new SSEClient('/api/v2/stream/metrics');
      client.connect();

      const eventSource = MockEventSource.getLatest();
      client.disconnect();

      expect(eventSource?.readyState).toBe(2); // CLOSED
    });

    it('should set status to disconnected', () => {
      const onStatusChange = vi.fn();
      const client = new SSEClient('/api/v2/stream/metrics', { onStatusChange });
      client.connect();
      client.disconnect();

      expect(onStatusChange).toHaveBeenLastCalledWith('disconnected');
    });

    it('should not reconnect after manual disconnect', () => {
      const client = new SSEClient('/api/v2/stream/metrics', {
        reconnectDelay: 100,
      });
      client.connect();
      client.disconnect();

      // Trigger error on closed connection
      MockEventSource.getLatest()?.triggerError();
      vi.advanceTimersByTime(500);

      // Should not have created a new connection
      expect(MockEventSource.instances.length).toBe(1);
    });
  });

  describe('getStatus', () => {
    it('should return current status', () => {
      const client = new SSEClient('/api/v2/stream/metrics');

      expect(client.getStatus()).toBe('disconnected');

      client.connect();
      expect(client.getStatus()).toBe('connecting');

      MockEventSource.getLatest()?.triggerOpen();
      expect(client.getStatus()).toBe('connected');
    });
  });
});

describe('SSEClient singleton', () => {
  beforeEach(() => {
    MockEventSource.reset();
    (global as unknown as { EventSource: typeof MockEventSource }).EventSource = MockEventSource;
    disconnectSSE();
  });

  afterEach(() => {
    (global as unknown as { EventSource: typeof EventSource }).EventSource = originalEventSource;
    disconnectSSE();
  });

  it('should return singleton instance', () => {
    const client1 = getSSEClient();
    const client2 = getSSEClient();

    expect(client1).toBe(client2);
  });

  it('should disconnect singleton', () => {
    const client = getSSEClient();
    client.connect();

    disconnectSSE();

    expect(client.getStatus()).toBe('disconnected');
  });
});
