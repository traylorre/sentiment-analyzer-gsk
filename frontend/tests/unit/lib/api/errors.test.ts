/**
 * Unit tests for auth error handlers (Feature 1190 / A23).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  AUTH_ERROR_MESSAGES,
  AUTH_ERROR_HANDLERS,
  isAuthError,
  handleAuthError,
  type AuthErrorCode,
} from '@/lib/api/errors';

// Mock the auth store
const mockReset = vi.fn();
const mockSetError = vi.fn();
const mockSetLoading = vi.fn();

vi.mock('@/stores/auth-store', () => ({
  useAuthStore: {
    getState: () => ({
      reset: mockReset,
      setError: mockSetError,
      setLoading: mockSetLoading,
    }),
  },
}));

// Mock window.location
const mockLocationHref = vi.fn();
const originalWindow = global.window;

describe('AUTH_ERROR_MESSAGES', () => {
  it('defines message for AUTH_013', () => {
    expect(AUTH_ERROR_MESSAGES.AUTH_013).toBe(
      'Your password was changed. Please sign in again.'
    );
  });

  it('defines message for AUTH_014', () => {
    expect(AUTH_ERROR_MESSAGES.AUTH_014).toBe(
      'You have been signed out because you logged in on another device.'
    );
  });

  it('defines message for AUTH_015', () => {
    expect(AUTH_ERROR_MESSAGES.AUTH_015).toBe(
      'This login provider is not supported.'
    );
  });

  it('defines message for AUTH_016', () => {
    expect(AUTH_ERROR_MESSAGES.AUTH_016).toBe('Login failed. Please try again.');
  });

  it('defines message for AUTH_017', () => {
    expect(AUTH_ERROR_MESSAGES.AUTH_017).toBe(
      'Password does not meet requirements.'
    );
  });

  it('defines message for AUTH_018', () => {
    expect(AUTH_ERROR_MESSAGES.AUTH_018).toBe(
      'Session expired. Please sign in again.'
    );
  });

  it('does not leak role information', () => {
    const forbiddenTerms = ['admin', 'operator', 'paid', 'free', 'tier', 'role'];
    Object.values(AUTH_ERROR_MESSAGES).forEach((message) => {
      const lowerMessage = message.toLowerCase();
      forbiddenTerms.forEach((term) => {
        expect(lowerMessage).not.toContain(term);
      });
    });
  });

  it('does not leak internal details', () => {
    const forbiddenTerms = [
      'dynamodb',
      'lambda',
      'cognito',
      'jwt',
      'database',
      'exception',
      'stack',
    ];
    Object.values(AUTH_ERROR_MESSAGES).forEach((message) => {
      const lowerMessage = message.toLowerCase();
      forbiddenTerms.forEach((term) => {
        expect(lowerMessage).not.toContain(term);
      });
    });
  });
});

describe('AUTH_ERROR_HANDLERS', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock window.location for redirect tests
    Object.defineProperty(global, 'window', {
      value: {
        location: {
          get href() {
            return '';
          },
          set href(value: string) {
            mockLocationHref(value);
          },
        },
      },
      writable: true,
    });
  });

  afterEach(() => {
    global.window = originalWindow;
  });

  it('handles AUTH_013 - clears tokens and redirects', () => {
    AUTH_ERROR_HANDLERS.AUTH_013();

    expect(mockReset).toHaveBeenCalled();
    expect(mockSetError).toHaveBeenCalledWith(AUTH_ERROR_MESSAGES.AUTH_013);
    expect(mockLocationHref).toHaveBeenCalledWith('/');
  });

  it('handles AUTH_014 - clears tokens and redirects', () => {
    AUTH_ERROR_HANDLERS.AUTH_014();

    expect(mockReset).toHaveBeenCalled();
    expect(mockSetError).toHaveBeenCalledWith(AUTH_ERROR_MESSAGES.AUTH_014);
    expect(mockLocationHref).toHaveBeenCalledWith('/');
  });

  it('handles AUTH_015 - shows error without redirect', () => {
    AUTH_ERROR_HANDLERS.AUTH_015();

    expect(mockSetError).toHaveBeenCalledWith(AUTH_ERROR_MESSAGES.AUTH_015);
    expect(mockReset).not.toHaveBeenCalled();
    expect(mockLocationHref).not.toHaveBeenCalled();
  });

  it('handles AUTH_016 - restarts OAuth flow', () => {
    AUTH_ERROR_HANDLERS.AUTH_016();

    expect(mockSetError).toHaveBeenCalledWith('Login failed. Please try again.');
    expect(mockSetLoading).toHaveBeenCalledWith(false);
    expect(mockReset).not.toHaveBeenCalled();
  });

  it('handles AUTH_017 - shows password requirements', () => {
    AUTH_ERROR_HANDLERS.AUTH_017();

    expect(mockSetError).toHaveBeenCalledWith(
      expect.stringContaining('8 characters')
    );
    expect(mockReset).not.toHaveBeenCalled();
  });

  it('handles AUTH_018 - clears tokens and redirects', () => {
    AUTH_ERROR_HANDLERS.AUTH_018();

    expect(mockReset).toHaveBeenCalled();
    expect(mockSetError).toHaveBeenCalledWith(AUTH_ERROR_MESSAGES.AUTH_018);
    expect(mockLocationHref).toHaveBeenCalledWith('/');
  });
});

describe('isAuthError', () => {
  it.each([
    'AUTH_013',
    'AUTH_014',
    'AUTH_015',
    'AUTH_016',
    'AUTH_017',
    'AUTH_018',
  ] as AuthErrorCode[])('returns true for %s', (code) => {
    expect(isAuthError(code)).toBe(true);
  });

  it('returns false for non-auth errors', () => {
    expect(isAuthError('NETWORK_ERROR')).toBe(false);
    expect(isAuthError('TIMEOUT')).toBe(false);
    expect(isAuthError('UNKNOWN')).toBe(false);
    expect(isAuthError('')).toBe(false);
  });

  it('returns false for unknown AUTH_ codes', () => {
    expect(isAuthError('AUTH_999')).toBe(false);
    expect(isAuthError('AUTH_001')).toBe(false);
  });
});

describe('handleAuthError', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(global, 'window', {
      value: {
        location: {
          get href() {
            return '';
          },
          set href(value: string) {
            mockLocationHref(value);
          },
        },
      },
      writable: true,
    });
  });

  afterEach(() => {
    global.window = originalWindow;
  });

  it('handles known auth error and returns true', () => {
    const result = handleAuthError('AUTH_013');

    expect(result).toBe(true);
    expect(mockReset).toHaveBeenCalled();
  });

  it('returns false for unknown error', () => {
    const result = handleAuthError('UNKNOWN_ERROR');

    expect(result).toBe(false);
    expect(mockReset).not.toHaveBeenCalled();
    expect(mockSetError).not.toHaveBeenCalled();
  });

  it('returns false for non-auth error codes', () => {
    const result = handleAuthError('NETWORK_ERROR');

    expect(result).toBe(false);
  });
});
