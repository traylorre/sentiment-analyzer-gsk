import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { emitErrorEvent } from '@/lib/api/client';

describe('emitErrorEvent', () => {
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-03-19T12:00:00.000Z'));
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    warnSpy.mockRestore();
    vi.useRealTimers();
  });

  it('should emit a JSON string via console.warn', () => {
    emitErrorEvent('api:unreachable', { endpoint: '/health' });

    expect(warnSpy).toHaveBeenCalledTimes(1);

    const output = warnSpy.mock.calls[0][0] as string;
    const parsed = JSON.parse(output);

    expect(parsed).toHaveProperty('event');
    expect(parsed).toHaveProperty('timestamp');
    expect(parsed).toHaveProperty('details');
  });

  it('should include the event name in the output', () => {
    emitErrorEvent('api:unreachable', { reason: 'timeout' });

    const parsed = JSON.parse(warnSpy.mock.calls[0][0] as string);
    expect(parsed.event).toBe('api:unreachable');
  });

  it('should include the details object', () => {
    const details = { endpoint: '/health', statusCode: 503 };
    emitErrorEvent('api:error', details);

    const parsed = JSON.parse(warnSpy.mock.calls[0][0] as string);
    expect(parsed.details).toEqual(details);
  });

  it('should produce an ISO 8601 timestamp', () => {
    emitErrorEvent('api:unreachable');

    const parsed = JSON.parse(warnSpy.mock.calls[0][0] as string);
    // Verify it matches ISO format and the frozen time
    expect(parsed.timestamp).toBe('2026-03-19T12:00:00.000Z');
    // Also verify it parses correctly
    expect(new Date(parsed.timestamp).toISOString()).toBe(parsed.timestamp);
  });

  it('should default to an empty details object when none provided', () => {
    emitErrorEvent('api:recovered');

    const parsed = JSON.parse(warnSpy.mock.calls[0][0] as string);
    expect(parsed.details).toEqual({});
  });
});
