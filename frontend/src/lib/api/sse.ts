/**
 * SSE (Server-Sent Events) client with automatic reconnection
 * for real-time sentiment updates
 */

export type SSEStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface SSEMessage<T = unknown> {
  type: string;
  data: T;
  timestamp: string;
}

export interface SentimentUpdatePayload {
  configId: string;
  ticker: string;
  source: string;
  sentiment: number;
  previousSentiment?: number;
  timestamp: string;
}

export interface SSEOptions {
  onMessage?: (message: SSEMessage) => void;
  onStatusChange?: (status: SSEStatus) => void;
  onError?: (error: Error) => void;
  reconnectAttempts?: number;
  reconnectDelay?: number;
  reconnectDelayMax?: number;
}

const DEFAULT_OPTIONS: Required<Pick<SSEOptions, 'reconnectAttempts' | 'reconnectDelay' | 'reconnectDelayMax'>> = {
  reconnectAttempts: 5,
  reconnectDelay: 1000,
  reconnectDelayMax: 30000,
};

export class SSEClient {
  private eventSource: EventSource | null = null;
  private url: string;
  private options: SSEOptions;
  private reconnectCount = 0;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private status: SSEStatus = 'disconnected';
  private isManuallyDisconnected = false;

  constructor(url: string, options: SSEOptions = {}) {
    this.url = url;
    this.options = { ...DEFAULT_OPTIONS, ...options };
  }

  private setStatus(status: SSEStatus) {
    if (this.status !== status) {
      this.status = status;
      this.options.onStatusChange?.(status);
    }
  }

  private getReconnectDelay(): number {
    const { reconnectDelay = DEFAULT_OPTIONS.reconnectDelay, reconnectDelayMax = DEFAULT_OPTIONS.reconnectDelayMax } = this.options;
    // Exponential backoff with jitter
    const exponentialDelay = reconnectDelay * Math.pow(2, this.reconnectCount);
    const jitter = Math.random() * 1000;
    return Math.min(exponentialDelay + jitter, reconnectDelayMax);
  }

  connect(): void {
    if (this.eventSource) {
      return; // Already connected
    }

    this.isManuallyDisconnected = false;
    this.setStatus('connecting');

    try {
      this.eventSource = new EventSource(this.url);

      this.eventSource.onopen = () => {
        this.reconnectCount = 0;
        this.setStatus('connected');
      };

      this.eventSource.onmessage = (event) => {
        try {
          const message: SSEMessage = JSON.parse(event.data);
          this.options.onMessage?.(message);
        } catch (error) {
          console.error('Failed to parse SSE message:', error);
        }
      };

      this.eventSource.onerror = () => {
        this.handleError();
      };

      // Listen for specific event types
      this.eventSource.addEventListener('sentiment_update', (event: MessageEvent) => {
        try {
          const data: SentimentUpdatePayload = JSON.parse(event.data);
          this.options.onMessage?.({
            type: 'sentiment_update',
            data,
            timestamp: new Date().toISOString(),
          });
        } catch (error) {
          console.error('Failed to parse sentiment_update event:', error);
        }
      });

      this.eventSource.addEventListener('heartbeat', () => {
        // Keep connection alive, no action needed
      });

    } catch (error) {
      this.setStatus('error');
      this.options.onError?.(error instanceof Error ? error : new Error('Failed to connect'));
      this.scheduleReconnect();
    }
  }

  private handleError(): void {
    if (this.isManuallyDisconnected) {
      return;
    }

    this.cleanup();
    this.setStatus('error');

    const { reconnectAttempts = DEFAULT_OPTIONS.reconnectAttempts } = this.options;

    if (this.reconnectCount < reconnectAttempts) {
      this.scheduleReconnect();
    } else {
      this.options.onError?.(new Error('Max reconnection attempts reached'));
    }
  }

  private scheduleReconnect(): void {
    if (this.isManuallyDisconnected) {
      return;
    }

    const delay = this.getReconnectDelay();
    this.reconnectCount++;

    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private cleanup(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  disconnect(): void {
    this.isManuallyDisconnected = true;
    this.cleanup();
    this.setStatus('disconnected');
    this.reconnectCount = 0;
  }

  getStatus(): SSEStatus {
    return this.status;
  }

  isConnected(): boolean {
    return this.status === 'connected';
  }
}

// Singleton instance for the main SSE connection
let sseInstance: SSEClient | null = null;

export function getSSEClient(baseUrl?: string): SSEClient {
  if (!sseInstance) {
    const url = baseUrl || `${process.env.NEXT_PUBLIC_API_URL || ''}/api/v2/stream/metrics`;
    sseInstance = new SSEClient(url);
  }
  return sseInstance;
}

export function disconnectSSE(): void {
  if (sseInstance) {
    sseInstance.disconnect();
    sseInstance = null;
  }
}
