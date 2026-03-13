/**
 * SSE Text Protocol Parser (T058)
 *
 * Parses SSE text protocol per the Server-Sent Events spec.
 * Handles `retry:`, `data:`, `id:`, `event:` fields.
 * Server emits `retry: 3000\n` as first field (FR-088, FR-089).
 *
 * Uses TextDecoder with `stream: true` for multi-byte UTF-8
 * chunk boundary correctness (FR-099).
 */

/** A fully parsed SSE event ready for consumption. */
export interface SSEEvent {
  /** Event type from `event:` field, defaults to "message". */
  type: string;
  /** Concatenated `data:` field values (joined with newlines). */
  data: string;
  /** Last `id:` field value, or undefined if not set. */
  lastEventId?: string;
  /** `retry:` value in milliseconds, or undefined if not set. */
  retry?: number;
}

/**
 * Stateful SSE text protocol parser.
 *
 * Feed chunks of bytes via `feed()` and receive parsed events
 * via the `onEvent` callback. Handles:
 * - Multi-byte UTF-8 across chunk boundaries (TextDecoder stream mode)
 * - Incomplete lines buffered across chunks
 * - Multiple events per chunk (double newline delimited)
 * - `retry:`, `data:`, `id:`, `event:` fields per SSE spec
 * - BOM stripping on first chunk
 */
export class SSEParser {
  private decoder = new TextDecoder('utf-8', { stream: true });
  private buffer = '';
  private eventType = '';
  private dataLines: string[] = [];
  private lastEventId: string | undefined;
  private retryMs: number | undefined;
  private firstChunk = true;

  /** Called when a complete event is parsed. */
  onEvent: ((event: SSEEvent) => void) | null = null;

  /** Called when a `retry:` field is received. */
  onRetry: ((ms: number) => void) | null = null;

  /**
   * Feed a chunk of bytes from a ReadableStream.
   * May emit zero or more events via `onEvent`.
   */
  feed(chunk: Uint8Array): void {
    let text = this.decoder.decode(chunk, { stream: true });

    // Strip BOM from first chunk
    if (this.firstChunk) {
      this.firstChunk = false;
      if (text.charCodeAt(0) === 0xfeff) {
        text = text.slice(1);
      }
    }

    this.buffer += text;
    this.processBuffer();
  }

  /** Flush any remaining buffered data (call on stream end). */
  flush(): void {
    // Decode any remaining bytes in the TextDecoder
    const remaining = this.decoder.decode(new Uint8Array(0), { stream: false });
    if (remaining) {
      this.buffer += remaining;
    }

    // Process any remaining lines
    if (this.buffer.length > 0) {
      // Add a trailing newline to process the last line
      this.buffer += '\n\n';
      this.processBuffer();
    }
  }

  /** Reset parser state for a new connection. */
  reset(): void {
    this.decoder = new TextDecoder('utf-8', { stream: true });
    this.buffer = '';
    this.eventType = '';
    this.dataLines = [];
    this.retryMs = undefined;
    this.firstChunk = true;
    // Preserve lastEventId across reconnections per SSE spec
  }

  private processBuffer(): void {
    // SSE uses \r\n, \r, or \n as line endings
    // Process complete lines, keep incomplete last line in buffer
    const lines = this.buffer.split(/\r\n|\r|\n/);

    // Last element is either empty (if buffer ended with newline) or
    // an incomplete line to keep buffered
    this.buffer = lines.pop() ?? '';

    for (const line of lines) {
      this.processLine(line);
    }
  }

  private processLine(line: string): void {
    // Empty line = dispatch event
    if (line === '') {
      this.dispatchEvent();
      return;
    }

    // Comment lines (start with colon) - ignore
    if (line.startsWith(':')) {
      return;
    }

    // Parse field:value
    const colonIdx = line.indexOf(':');
    let field: string;
    let value: string;

    if (colonIdx === -1) {
      // Field with no value
      field = line;
      value = '';
    } else {
      field = line.slice(0, colonIdx);
      // Skip single leading space after colon per SSE spec
      value = line.charAt(colonIdx + 1) === ' '
        ? line.slice(colonIdx + 2)
        : line.slice(colonIdx + 1);
    }

    switch (field) {
      case 'event':
        this.eventType = value;
        break;
      case 'data':
        this.dataLines.push(value);
        break;
      case 'id':
        // SSE spec: id field must not contain null
        if (!value.includes('\0')) {
          this.lastEventId = value;
        }
        break;
      case 'retry': {
        const ms = parseInt(value, 10);
        if (!isNaN(ms) && ms >= 0 && String(ms) === value.trim()) {
          this.retryMs = ms;
          this.onRetry?.(ms);
        }
        break;
      }
      // Unknown fields are ignored per SSE spec
    }
  }

  private dispatchEvent(): void {
    // Only dispatch if we have data lines
    if (this.dataLines.length === 0) {
      this.eventType = '';
      return;
    }

    const event: SSEEvent = {
      type: this.eventType || 'message',
      data: this.dataLines.join('\n'),
      lastEventId: this.lastEventId,
      retry: this.retryMs,
    };

    this.onEvent?.(event);

    // Reset per-event state (but not lastEventId or retry)
    this.eventType = '';
    this.dataLines = [];
  }
}
