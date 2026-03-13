/**
 * SSE Connection State Machine (T059, T060)
 *
 * States: connected, reconnecting, disconnected, error
 *
 * Error categories per FR-118:
 * - graceful_close: Server-initiated (e.g., deadline event)
 * - abnormal_termination: Unexpected stream end
 * - network_error: Network failure
 * - intentional_cancellation: User/component-initiated disconnect
 *
 * Reconnection with exponential backoff + jitter (T060):
 * - Propagates Last-Event-ID header (FR-081)
 * - Generates session_id (FR-048)
 * - Tracks connection_sequence counter
 * - Extracts previous_trace_id from response headers (FR-033)
 */

import { SSEParser, type SSEEvent } from './sse-parser';

// ===================================================================
// Types
// ===================================================================

export type ConnectionState = 'connected' | 'reconnecting' | 'disconnected' | 'error';

export type ErrorCategory =
  | 'graceful_close'
  | 'abnormal_termination'
  | 'network_error'
  | 'intentional_cancellation';

export interface ConnectionInfo {
  state: ConnectionState;
  sessionId: string;
  connectionSequence: number;
  lastEventId?: string;
  previousTraceId?: string;
  errorCategory?: ErrorCategory;
}

export interface SSEConnectionOptions {
  /** URL to connect to. */
  url: string;
  /** Additional headers to include on every request. */
  headers?: Record<string, string>;
  /** Maximum reconnection attempts before entering error state (default: 10). */
  maxReconnectAttempts?: number;
  /** Base delay in ms for exponential backoff (default: 1000). */
  baseDelay?: number;
  /** Maximum delay in ms for backoff (default: 30000). */
  maxDelay?: number;
  /** Short delay in ms for graceful close reconnection (default: 500). */
  gracefulCloseDelay?: number;

  // Callbacks
  onEvent?: (event: SSEEvent) => void;
  onStateChange?: (info: ConnectionInfo) => void;
  onRetry?: (ms: number) => void;
}

// ===================================================================
// Implementation
// ===================================================================

function generateSessionId(): string {
  return crypto.randomUUID();
}

export class SSEConnection {
  private options: Required<
    Pick<SSEConnectionOptions, 'maxReconnectAttempts' | 'baseDelay' | 'maxDelay' | 'gracefulCloseDelay'>
  > & SSEConnectionOptions;

  private state: ConnectionState = 'disconnected';
  private sessionId: string;
  private connectionSequence = 0;
  private lastEventId: string | undefined;
  private previousTraceId: string | undefined;
  private serverRetryMs: number | undefined;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private abortController: AbortController | null = null;
  private parser: SSEParser;

  constructor(options: SSEConnectionOptions) {
    this.options = {
      maxReconnectAttempts: 10,
      baseDelay: 1000,
      maxDelay: 30000,
      gracefulCloseDelay: 500,
      ...options,
    };
    this.sessionId = generateSessionId();
    this.parser = new SSEParser();

    this.parser.onEvent = (event) => this.handleEvent(event);
    this.parser.onRetry = (ms) => {
      this.serverRetryMs = ms;
      this.options.onRetry?.(ms);
    };
  }

  /** Start the connection. */
  async connect(): Promise<void> {
    if (this.state === 'connected') return;

    this.abortController = new AbortController();
    this.setState('reconnecting');

    try {
      await this.doConnect();
    } catch (err) {
      if (this.abortController?.signal.aborted) return;
      this.handleConnectionError(err, 'network_error');
    }
  }

  /** Disconnect and stop reconnecting. */
  disconnect(): void {
    this.clearReconnectTimer();
    this.abortController?.abort();
    this.abortController = null;
    this.parser.reset();
    this.setState('disconnected', 'intentional_cancellation');
    this.reconnectAttempts = 0;
  }

  /** Get current connection info. */
  getInfo(): ConnectionInfo {
    return {
      state: this.state,
      sessionId: this.sessionId,
      connectionSequence: this.connectionSequence,
      lastEventId: this.lastEventId,
      previousTraceId: this.previousTraceId,
    };
  }

  // ---------------------------------------------------------------
  // Internal
  // ---------------------------------------------------------------

  private async doConnect(): Promise<void> {
    const headers: Record<string, string> = {
      Accept: 'text/event-stream',
      'Cache-Control': 'no-cache',
      ...this.options.headers,
    };

    if (this.lastEventId) {
      headers['Last-Event-ID'] = this.lastEventId;
    }

    this.connectionSequence++;
    this.parser.reset();

    const response = await fetch(this.options.url, {
      headers,
      signal: this.abortController!.signal,
    });

    if (!response.ok) {
      throw new Error(`SSE connection failed: ${response.status}`);
    }

    // Extract trace ID from response (FR-033)
    const traceId = response.headers.get('X-Amzn-Trace-Id');
    if (traceId) {
      this.previousTraceId = traceId;
    }

    this.reconnectAttempts = 0;
    this.setState('connected');

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('Response body is not readable');
    }

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        this.parser.feed(value);
      }

      // Stream ended normally
      this.parser.flush();
      this.handleConnectionError(null, 'abnormal_termination');
    } catch (err) {
      if (this.abortController?.signal.aborted) return;
      this.handleConnectionError(err, 'network_error');
    } finally {
      reader.releaseLock();
    }
  }

  private handleEvent(event: SSEEvent): void {
    if (event.lastEventId !== undefined) {
      this.lastEventId = event.lastEventId;
    }

    // Handle deadline event: server-initiated graceful close (FR-100)
    if (event.type === 'deadline') {
      this.parser.flush();
      this.scheduleReconnect('graceful_close');
      return;
    }

    this.options.onEvent?.(event);
  }

  private handleConnectionError(
    _err: unknown,
    category: ErrorCategory,
  ): void {
    if (category === 'intentional_cancellation') return;
    this.scheduleReconnect(category);
  }

  private scheduleReconnect(category: ErrorCategory): void {
    this.clearReconnectTimer();

    if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      this.setState('error', category);
      return;
    }

    this.setState('reconnecting', category);
    const delay = this.getReconnectDelay(category);
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private getReconnectDelay(category: ErrorCategory): number {
    // Graceful close: short delay, not exponential (FR-100)
    if (category === 'graceful_close') {
      return this.options.gracefulCloseDelay;
    }

    // Server-specified retry takes precedence
    if (this.serverRetryMs !== undefined) {
      return this.serverRetryMs;
    }

    // Exponential backoff with jitter
    const exponential = this.options.baseDelay * Math.pow(2, this.reconnectAttempts);
    const jitter = Math.random() * this.options.baseDelay;
    return Math.min(exponential + jitter, this.options.maxDelay);
  }

  private setState(state: ConnectionState, errorCategory?: ErrorCategory): void {
    this.state = state;
    this.options.onStateChange?.({
      state,
      sessionId: this.sessionId,
      connectionSequence: this.connectionSequence,
      lastEventId: this.lastEventId,
      previousTraceId: this.previousTraceId,
      errorCategory,
    });
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}
