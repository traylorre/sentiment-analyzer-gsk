/**
 * Market calendar utilities for detecting trading gaps.
 *
 * Used to identify and fill non-trading periods (weekends, holidays)
 * for proper chart visualization with gap markers.
 */

import type { GapMarker, OHLCResolution, PriceCandle } from '@/types/chart';

/**
 * US Stock Market holidays (NYSE/NASDAQ).
 * Dates are in MM-DD format for fixed holidays, or computed for floating holidays.
 */
interface Holiday {
  name: string;
  /** For fixed-date holidays like Independence Day */
  fixedDate?: string; // MM-DD format
  /** For floating holidays like Thanksgiving */
  compute?: (year: number) => string; // Returns YYYY-MM-DD
}

const US_MARKET_HOLIDAYS: Holiday[] = [
  { name: "New Year's Day", fixedDate: '01-01' },
  {
    name: 'Martin Luther King Jr. Day',
    compute: (year) => getNthWeekdayOfMonth(year, 1, 1, 3), // 3rd Monday of January
  },
  {
    name: "Presidents' Day",
    compute: (year) => getNthWeekdayOfMonth(year, 2, 1, 3), // 3rd Monday of February
  },
  {
    name: 'Good Friday',
    compute: (year) => getGoodFriday(year),
  },
  {
    name: 'Memorial Day',
    compute: (year) => getLastWeekdayOfMonth(year, 5, 1), // Last Monday of May
  },
  { name: 'Juneteenth', fixedDate: '06-19' },
  { name: 'Independence Day', fixedDate: '07-04' },
  {
    name: 'Labor Day',
    compute: (year) => getNthWeekdayOfMonth(year, 9, 1, 1), // 1st Monday of September
  },
  {
    name: 'Thanksgiving Day',
    compute: (year) => getNthWeekdayOfMonth(year, 11, 4, 4), // 4th Thursday of November
  },
  { name: 'Christmas Day', fixedDate: '12-25' },
];

/**
 * Get the Nth weekday of a month (e.g., 3rd Monday of January).
 */
function getNthWeekdayOfMonth(
  year: number,
  month: number,
  weekday: number,
  n: number
): string {
  const firstDay = new Date(year, month - 1, 1);
  let count = 0;
  for (let day = 1; day <= 31; day++) {
    const date = new Date(year, month - 1, day);
    if (date.getMonth() !== month - 1) break;
    if (date.getDay() === weekday) {
      count++;
      if (count === n) {
        return formatDateYYYYMMDD(date);
      }
    }
  }
  throw new Error(`Could not find ${n}th weekday ${weekday} in ${month}/${year}`);
}

/**
 * Get the last weekday of a month (e.g., last Monday of May).
 */
function getLastWeekdayOfMonth(year: number, month: number, weekday: number): string {
  const lastDay = new Date(year, month, 0); // Last day of month
  for (let day = lastDay.getDate(); day >= 1; day--) {
    const date = new Date(year, month - 1, day);
    if (date.getDay() === weekday) {
      return formatDateYYYYMMDD(date);
    }
  }
  throw new Error(`Could not find last weekday ${weekday} in ${month}/${year}`);
}

/**
 * Calculate Good Friday (2 days before Easter Sunday).
 * Uses the Anonymous Gregorian algorithm.
 */
function getGoodFriday(year: number): string {
  // Calculate Easter Sunday using Anonymous Gregorian algorithm
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31);
  const day = ((h + l - 7 * m + 114) % 31) + 1;

  // Good Friday is 2 days before Easter
  const easter = new Date(year, month - 1, day);
  easter.setDate(easter.getDate() - 2);
  return formatDateYYYYMMDD(easter);
}

function formatDateYYYYMMDD(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Cache for holiday dates by year.
 */
const holidayCache: Map<number, Map<string, string>> = new Map();

/**
 * Get all holidays for a given year as a Map<date, holidayName>.
 */
function getHolidaysForYear(year: number): Map<string, string> {
  if (holidayCache.has(year)) {
    return holidayCache.get(year)!;
  }

  const holidays = new Map<string, string>();
  for (const holiday of US_MARKET_HOLIDAYS) {
    let dateStr: string;
    if (holiday.fixedDate) {
      dateStr = `${year}-${holiday.fixedDate}`;
    } else if (holiday.compute) {
      dateStr = holiday.compute(year);
    } else {
      continue;
    }

    // Handle observed holidays (if falls on weekend, observed on adjacent weekday)
    const date = new Date(dateStr);
    const dayOfWeek = date.getDay();

    if (dayOfWeek === 0) {
      // Sunday: observed on Monday
      date.setDate(date.getDate() + 1);
      dateStr = formatDateYYYYMMDD(date);
    } else if (dayOfWeek === 6) {
      // Saturday: observed on Friday
      date.setDate(date.getDate() - 1);
      dateStr = formatDateYYYYMMDD(date);
    }

    holidays.set(dateStr, holiday.name);
  }

  holidayCache.set(year, holidays);
  return holidays;
}

/**
 * Check if a given date is a US market holiday.
 */
export function isHoliday(date: Date): { isHoliday: boolean; name?: string } {
  const dateStr = formatDateYYYYMMDD(date);
  const holidays = getHolidaysForYear(date.getFullYear());
  const holidayName = holidays.get(dateStr);
  return holidayName ? { isHoliday: true, name: holidayName } : { isHoliday: false };
}

/**
 * Check if a date is a weekend (Saturday or Sunday).
 */
export function isWeekend(date: Date): boolean {
  const day = date.getDay();
  return day === 0 || day === 6;
}

/**
 * Check if the US stock market is open for a given date/time.
 *
 * @param date - Date to check
 * @param resolution - OHLC resolution for time-based checks
 * @returns Object with isOpen boolean and reason if closed
 */
export function isMarketOpen(
  date: Date,
  resolution: OHLCResolution
): { isOpen: boolean; reason?: 'weekend' | 'holiday' | 'after_hours'; holidayName?: string } {
  // Check weekend
  if (isWeekend(date)) {
    return { isOpen: false, reason: 'weekend' };
  }

  // Check holiday
  const holiday = isHoliday(date);
  if (holiday.isHoliday) {
    return { isOpen: false, reason: 'holiday', holidayName: holiday.name };
  }

  // For intraday resolutions, check market hours (9:30 AM - 4:00 PM ET)
  if (resolution !== 'D') {
    const hours = date.getHours();
    const minutes = date.getMinutes();
    const timeInMinutes = hours * 60 + minutes;

    // Market hours: 9:30 AM (570 min) to 4:00 PM (960 min) Eastern Time
    // Note: This assumes the date is already in Eastern Time or UTC
    const marketOpen = 9 * 60 + 30; // 9:30 AM
    const marketClose = 16 * 60; // 4:00 PM

    if (timeInMinutes < marketOpen || timeInMinutes >= marketClose) {
      return { isOpen: false, reason: 'after_hours' };
    }
  }

  return { isOpen: true };
}

/**
 * Get all dates between two dates (exclusive of start and end).
 */
function getDatesBetween(startDate: Date, endDate: Date): Date[] {
  const dates: Date[] = [];
  const current = new Date(startDate);
  current.setDate(current.getDate() + 1);

  while (current < endDate) {
    dates.push(new Date(current));
    current.setDate(current.getDate() + 1);
  }

  return dates;
}

/**
 * Fill gaps in candle data with GapMarker entries.
 *
 * Inserts markers for weekends and holidays between trading days.
 * This enables the chart to display red-shaded rectangles for market closures.
 *
 * @param candles - Array of OHLC candles from the API
 * @param resolution - OHLC resolution
 * @returns Array of candles and gap markers, maintaining chronological order
 */
export function fillGaps(
  candles: PriceCandle[],
  resolution: OHLCResolution
): (PriceCandle | GapMarker)[] {
  if (candles.length < 2) {
    return candles;
  }

  const result: (PriceCandle | GapMarker)[] = [];

  for (let i = 0; i < candles.length; i++) {
    // Add the current candle
    result.push(candles[i]);

    // Check for gaps before the next candle
    if (i < candles.length - 1) {
      const currentDate = new Date(candles[i].date);
      const nextDate = new Date(candles[i + 1].date);

      // Get dates between current and next candle
      const betweenDates = getDatesBetween(currentDate, nextDate);

      for (const date of betweenDates) {
        const marketStatus = isMarketOpen(date, resolution);

        if (!marketStatus.isOpen && marketStatus.reason) {
          // Only add gap markers for closed market days
          const gapMarker: GapMarker = {
            time: formatDateYYYYMMDD(date),
            isGap: true,
            reason: marketStatus.reason,
          };

          if (marketStatus.holidayName) {
            gapMarker.holidayName = marketStatus.holidayName;
          }

          result.push(gapMarker);
        }
      }
    }
  }

  return result;
}

/**
 * Extract gap markers from a mixed array of candles and gap markers.
 */
export function extractGapMarkers(data: (PriceCandle | GapMarker)[]): GapMarker[] {
  return data.filter((item): item is GapMarker => 'isGap' in item && item.isGap);
}

/**
 * Get the index positions of gaps in the data array.
 * Used by the GapShaderPrimitive to know where to draw rectangles.
 */
export function getGapIndices(data: (PriceCandle | GapMarker)[]): number[] {
  const indices: number[] = [];
  for (let i = 0; i < data.length; i++) {
    const item = data[i];
    if ('isGap' in item && item.isGap) {
      indices.push(i);
    }
  }
  return indices;
}

/**
 * Check if a data point is a GapMarker.
 */
export function isGapMarker(item: PriceCandle | GapMarker): item is GapMarker {
  return 'isGap' in item && item.isGap === true;
}
