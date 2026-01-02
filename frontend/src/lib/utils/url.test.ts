import { describe, it, expect } from 'vitest';
import { joinUrl } from './url';

describe('joinUrl', () => {
  describe('standard cases', () => {
    it('joins base URL without trailing slash and path with leading slash', () => {
      expect(joinUrl('https://a.com', '/path')).toBe('https://a.com/path');
    });

    it('joins base URL with trailing slash and path with leading slash', () => {
      expect(joinUrl('https://a.com/', '/path')).toBe('https://a.com/path');
    });

    it('joins base URL without trailing slash and path without leading slash', () => {
      expect(joinUrl('https://a.com', 'path')).toBe('https://a.com/path');
    });

    it('joins base URL with trailing slash and path without leading slash', () => {
      expect(joinUrl('https://a.com/', 'path')).toBe('https://a.com/path');
    });
  });

  describe('multiple slashes', () => {
    it('handles multiple trailing slashes on base URL', () => {
      expect(joinUrl('https://a.com//', '//path')).toBe('https://a.com/path');
    });

    it('handles many trailing slashes on base URL', () => {
      expect(joinUrl('https://a.com///', 'path')).toBe('https://a.com/path');
    });

    it('handles many leading slashes on path', () => {
      expect(joinUrl('https://a.com', '///path')).toBe('https://a.com/path');
    });
  });

  describe('edge cases', () => {
    it('returns base URL without trailing slash when path is empty', () => {
      expect(joinUrl('https://a.com', '')).toBe('https://a.com');
    });

    it('returns base URL without trailing slash when path is empty and base has trailing slash', () => {
      expect(joinUrl('https://a.com/', '')).toBe('https://a.com');
    });

    it('throws error when base URL is empty', () => {
      expect(() => joinUrl('', '/path')).toThrow('API base URL is required');
    });
  });

  describe('real-world scenarios', () => {
    it('handles Lambda Function URL format', () => {
      const lambdaUrl = 'https://abc123.lambda-url.us-east-1.on.aws';
      expect(joinUrl(lambdaUrl, '/api/v2/auth/anonymous')).toBe(
        'https://abc123.lambda-url.us-east-1.on.aws/api/v2/auth/anonymous'
      );
    });

    it('handles Lambda Function URL with trailing slash', () => {
      const lambdaUrl = 'https://abc123.lambda-url.us-east-1.on.aws/';
      expect(joinUrl(lambdaUrl, '/api/v2/auth/anonymous')).toBe(
        'https://abc123.lambda-url.us-east-1.on.aws/api/v2/auth/anonymous'
      );
    });

    it('handles localhost development URL', () => {
      expect(joinUrl('http://localhost:8000', '/api/v2/runtime')).toBe(
        'http://localhost:8000/api/v2/runtime'
      );
    });

    it('preserves query parameters in path', () => {
      expect(joinUrl('https://a.com', '/api?foo=bar')).toBe(
        'https://a.com/api?foo=bar'
      );
    });
  });
});
