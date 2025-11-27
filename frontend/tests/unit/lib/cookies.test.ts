import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  setAuthCookies,
  clearAuthCookies,
  getAuthCookie,
  getIsAnonymousCookie,
} from '@/lib/cookies';

describe('Cookie Utilities', () => {
  let originalCookie: string;
  let cookieStore: string;

  beforeEach(() => {
    originalCookie = document.cookie;
    cookieStore = '';

    // Mock document.cookie
    Object.defineProperty(document, 'cookie', {
      get: () => cookieStore,
      set: (value: string) => {
        // Parse the cookie and update store
        const [cookiePart] = value.split(';');
        const [name, val] = cookiePart.split('=');

        if (value.includes('expires=Thu, 01 Jan 1970')) {
          // Remove cookie
          const regex = new RegExp(`${name}=[^;]*;?\\s*`);
          cookieStore = cookieStore.replace(regex, '').trim();
        } else {
          // Add/update cookie
          const regex = new RegExp(`${name}=[^;]*`);
          if (regex.test(cookieStore)) {
            cookieStore = cookieStore.replace(regex, `${name}=${val}`);
          } else {
            cookieStore = cookieStore
              ? `${cookieStore}; ${name}=${val}`
              : `${name}=${val}`;
          }
        }
      },
      configurable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(document, 'cookie', {
      value: originalCookie,
      writable: true,
      configurable: true,
    });
  });

  describe('setAuthCookies', () => {
    it('should set access token cookie', () => {
      setAuthCookies('test-token-123', false);

      expect(cookieStore).toContain('sentiment-access-token=test-token-123');
    });

    it('should set anonymous flag cookie to false', () => {
      setAuthCookies('test-token-123', false);

      expect(cookieStore).toContain('sentiment-is-anonymous=false');
    });

    it('should set anonymous flag cookie to true', () => {
      setAuthCookies('test-token-123', true);

      expect(cookieStore).toContain('sentiment-is-anonymous=true');
    });
  });

  describe('clearAuthCookies', () => {
    it('should clear auth cookies', () => {
      // Set cookies first
      setAuthCookies('test-token', false);
      expect(cookieStore).toContain('sentiment-access-token');

      // Clear cookies
      clearAuthCookies();

      expect(cookieStore).not.toContain('sentiment-access-token=test-token');
    });
  });

  describe('getAuthCookie', () => {
    it('should return access token when set', () => {
      setAuthCookies('my-access-token', false);

      const token = getAuthCookie();

      expect(token).toBe('my-access-token');
    });

    it('should return null when no token', () => {
      cookieStore = '';

      const token = getAuthCookie();

      expect(token).toBeNull();
    });
  });

  describe('getIsAnonymousCookie', () => {
    it('should return true when anonymous', () => {
      setAuthCookies('token', true);

      const isAnon = getIsAnonymousCookie();

      expect(isAnon).toBe(true);
    });

    it('should return false when not anonymous', () => {
      setAuthCookies('token', false);

      const isAnon = getIsAnonymousCookie();

      expect(isAnon).toBe(false);
    });

    it('should return false when no cookie', () => {
      cookieStore = '';

      const isAnon = getIsAnonymousCookie();

      expect(isAnon).toBe(false);
    });
  });

  describe('SSR safety', () => {
    it('should handle server-side rendering gracefully', () => {
      // Save original document
      const originalDocument = global.document;

      // Simulate SSR by making document undefined
      // @ts-expect-error - Testing SSR scenario
      delete global.document;

      // These should not throw
      expect(() => setAuthCookies('token', false)).not.toThrow();
      expect(() => clearAuthCookies()).not.toThrow();
      expect(getAuthCookie()).toBeNull();
      expect(getIsAnonymousCookie()).toBe(false);

      // Restore document
      global.document = originalDocument;
    });
  });
});
