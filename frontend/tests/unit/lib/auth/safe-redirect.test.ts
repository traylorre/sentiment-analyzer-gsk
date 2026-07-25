import { describe, it, expect } from 'vitest';
import { safeInternalPath } from '@/lib/auth/safe-redirect';

describe('safeInternalPath — Feature 1394 open-redirect guard', () => {
  describe('accepts same-origin internal paths', () => {
    it('returns a rooted path unchanged', () => {
      expect(safeInternalPath('/settings')).toBe('/settings');
    });

    it('preserves query strings', () => {
      expect(safeInternalPath('/configs?tab=alerts')).toBe('/configs?tab=alerts');
    });

    it('preserves nested paths and hashes', () => {
      expect(safeInternalPath('/alerts/123#top')).toBe('/alerts/123#top');
    });

    it('allows the root path', () => {
      expect(safeInternalPath('/')).toBe('/');
    });
  });

  describe('rejects open-redirect payloads (falls back to /)', () => {
    it('rejects protocol-relative //evil.com', () => {
      expect(safeInternalPath('//evil.com')).toBe('/');
    });

    it('rejects an absolute https URL', () => {
      expect(safeInternalPath('https://evil.com')).toBe('/');
    });

    it('rejects an absolute http URL', () => {
      expect(safeInternalPath('http://evil.com/path')).toBe('/');
    });

    it('rejects the backslash protocol-relative variant', () => {
      expect(safeInternalPath('/\\evil.com')).toBe('/');
    });

    it('rejects javascript: scheme', () => {
      expect(safeInternalPath('javascript:alert(1)')).toBe('/');
    });

    it('rejects a bare relative segment (no leading slash)', () => {
      expect(safeInternalPath('settings')).toBe('/');
    });
  });

  describe('rejects control-char smuggling (tab/CR/LF stripped by the URL parser)', () => {
    // Regression: browsers strip \t \r \n before URL resolution, so these pass a
    // naive startsWith('//') check but resolve to //evil.com and navigate off-site.
    it.each([
      ['/\t/evil.com'],
      ['/\t//evil.com'],
      ['/\n//evil.com'],
      ['/\r//evil.com'],
      ['/\t\\evil.com'],
      ['/\r\n//evil.com'],
    ])('neutralizes %j to /', (payload) => {
      expect(safeInternalPath(payload)).toBe('/');
    });

    it('still accepts a legit path after control-char stripping is a no-op', () => {
      expect(safeInternalPath('/alerts?x=1#y')).toBe('/alerts?x=1#y');
    });
  });

  describe('rejects dot-segment collapse to a protocol-relative path', () => {
    // Regression: `/..//evil.com` passes the `//` prefix check, but URL
    // normalization pops the empty segment leaving pathname `//evil.com`.
    it.each([
      ['/..//evil.com'],
      ['/./..//evil.com'],
      ['/../..//evil.com'],
      ['/foo/../..//evil.com'],
    ])('neutralizes %j to /', (payload) => {
      expect(safeInternalPath(payload)).toBe('/');
    });

    it('still allows a legit dot-segment that stays same-origin', () => {
      expect(safeInternalPath('/foo/../alerts')).toBe('/alerts');
    });
  });

  describe('edge cases', () => {
    it('falls back on null', () => {
      expect(safeInternalPath(null)).toBe('/');
    });

    it('falls back on undefined', () => {
      expect(safeInternalPath(undefined)).toBe('/');
    });

    it('falls back on empty string', () => {
      expect(safeInternalPath('')).toBe('/');
    });

    it('honors a custom fallback', () => {
      expect(safeInternalPath('//evil.com', '/home')).toBe('/home');
    });
  });
});
