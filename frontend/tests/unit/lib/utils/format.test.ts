import { describe, it, expect } from 'vitest';
import {
  formatNumber,
  formatSentimentScore,
  formatPercent,
  formatDate,
  formatDateTime,
  formatRelativeTime,
  formatCountdown,
  formatChartDate,
} from '@/lib/utils/format';

describe('format utilities', () => {
  describe('formatNumber', () => {
    it('should format number with default 2 decimals', () => {
      expect(formatNumber(123.456)).toBe('123.46');
    });

    it('should format number with custom decimals', () => {
      expect(formatNumber(123.456, 1)).toBe('123.5');
    });
  });

  describe('formatSentimentScore', () => {
    it('should format positive score with + sign', () => {
      expect(formatSentimentScore(0.75)).toBe('+0.75');
    });

    it('should format negative score without + sign', () => {
      expect(formatSentimentScore(-0.25)).toBe('-0.25');
    });

    it('should format zero with + sign', () => {
      expect(formatSentimentScore(0)).toBe('+0.00');
    });
  });

  describe('formatPercent', () => {
    it('should format decimal as percentage', () => {
      expect(formatPercent(0.75)).toBe('75.0%');
    });

    it('should format with custom decimals', () => {
      expect(formatPercent(0.755, 2)).toBe('75.50%');
    });
  });

  describe('formatCountdown', () => {
    it('should format seconds as MM:SS', () => {
      expect(formatCountdown(125)).toBe('2:05');
    });

    it('should handle zero seconds', () => {
      expect(formatCountdown(0)).toBe('0:00');
    });
  });

  describe('formatChartDate', () => {
    describe('T090: Intraday resolution with Unix timestamp', () => {
      it('should format Unix timestamp for 1-minute resolution', () => {
        // Dec 23, 2024 14:30:00 UTC = 1734963000
        const timestamp = 1734963000;
        const result = formatChartDate(timestamp, '1');
        // Should include weekday, date, and time
        expect(result).toMatch(/Mon/);
        expect(result).toMatch(/12\/23/);
        // Time part varies by timezone, just check it exists
        expect(result).toMatch(/\d{1,2}:\d{2}/);
      });

      it('should format Unix timestamp for 5-minute resolution', () => {
        const timestamp = 1734963000;
        const result = formatChartDate(timestamp, '5');
        expect(result).toMatch(/Mon/);
        expect(result).toMatch(/\d{1,2}:\d{2}/);
      });

      it('should format Unix timestamp for 1-hour resolution', () => {
        const timestamp = 1734963000;
        const result = formatChartDate(timestamp, '60');
        expect(result).toMatch(/Mon/);
        expect(result).toMatch(/\d{1,2}:\d{2}/);
      });
    });

    describe('T091: Daily resolution with date string', () => {
      it('should format YYYY-MM-DD string for daily resolution', () => {
        const dateStr = '2024-12-23';
        const result = formatChartDate(dateStr, 'D');
        // Should include weekday and date but NOT time
        // Note: Exact weekday depends on timezone, just verify format
        expect(result).toMatch(/\w{3}/); // Weekday abbreviation
        expect(result).toMatch(/Dec/);
        // Date may be 22 or 23 depending on timezone
        expect(result).toMatch(/2[23]/);
        // Should NOT include time for daily
        expect(result).not.toMatch(/\d{1,2}:\d{2}/);
      });

      it('should handle ISO datetime string for daily resolution', () => {
        const dateStr = '2024-12-23T14:30:00Z';
        const result = formatChartDate(dateStr, 'D');
        expect(result).toMatch(/\w{3}/); // Weekday
        expect(result).toMatch(/Dec/);
        // Should NOT include time even though input has time
        expect(result).not.toMatch(/\d{1,2}:\d{2}/);
      });
    });

    describe('T092-T093: Mixed time type handling', () => {
      it('should handle numeric time without error', () => {
        expect(() => formatChartDate(1734963000, '60')).not.toThrow();
      });

      it('should handle string time without error', () => {
        expect(() => formatChartDate('2024-12-23', 'D')).not.toThrow();
      });

      it('should handle numeric time for daily resolution', () => {
        // Edge case: numeric timestamp with daily resolution
        const timestamp = 1734912000; // Dec 23, 2024 00:00:00 UTC
        const result = formatChartDate(timestamp, 'D');
        // Should still work, format as daily (no time)
        expect(result).toMatch(/Dec/);
        expect(result).not.toMatch(/\d{1,2}:\d{2}/);
      });

      it('should handle string time for intraday resolution', () => {
        // Edge case: ISO string with intraday resolution
        const dateStr = '2024-12-23T14:30:00Z';
        const result = formatChartDate(dateStr, '60');
        // Should include time
        expect(result).toMatch(/\d{1,2}:\d{2}/);
      });
    });

    describe('T094-T095: Format output validation', () => {
      it('should include time for all intraday resolutions', () => {
        const timestamp = 1734963000;
        const intradayResolutions: Array<'1' | '5' | '15' | '30' | '60'> = ['1', '5', '15', '30', '60'];

        for (const res of intradayResolutions) {
          const result = formatChartDate(timestamp, res);
          expect(result).toMatch(/\d{1,2}:\d{2}/);
        }
      });

      it('should exclude time for daily resolution', () => {
        const dateStr = '2024-12-23';
        const result = formatChartDate(dateStr, 'D');
        expect(result).not.toMatch(/\d{1,2}:\d{2} [AP]M/);
      });
    });

    describe('Edge cases', () => {
      it('should handle midnight timestamps', () => {
        const midnight = 1734912000; // Dec 23, 2024 00:00:00 UTC
        const result = formatChartDate(midnight, '60');
        // Should still format correctly
        expect(result).toMatch(/Mon|Sun/); // Could be either depending on timezone
      });

      it('should handle year boundary', () => {
        const newYear = 1735689600; // Jan 1, 2025 00:00:00 UTC
        const result = formatChartDate(newYear, 'D');
        // May show Dec 31 or Jan 1 depending on local timezone offset from UTC
        expect(result).toMatch(/Dec|Jan/);
        expect(result).toMatch(/\d{1,2}/);
      });
    });
  });
});
