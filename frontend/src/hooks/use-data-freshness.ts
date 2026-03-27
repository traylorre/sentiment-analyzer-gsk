'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { REFRESH_INTERVAL_SECONDS } from '@/lib/constants';

/**
 * Data freshness tracking hook (Feature 1266).
 *
 * Calculates data age from a server-provided timestamp, determines
 * staleness state, and formats a human-readable relative time string.
 *
 * - Updates once per minute via setInterval
 * - Recalculates immediately on visibilitychange (backgrounded tab return)
 * - Handles clock skew: clamps negative age to 0, falls back to client
 *   time if server timestamp is >5 min in the future
 * - Thresholds are multiples of REFRESH_INTERVAL_SECONDS (not hardcoded)
 */

export type FreshnessState = 'loading' | 'fresh' | 'stale' | 'critical';

const REFRESH_INTERVAL_MS = REFRESH_INTERVAL_SECONDS * 1000;
const STALE_THRESHOLD_MS = REFRESH_INTERVAL_MS * 2;
const CRITICAL_THRESHOLD_MS = REFRESH_INTERVAL_MS * 4;
const MAX_CLOCK_SKEW_MS = 5 * 60 * 1000;

interface DataFreshnessResult {
  ageMs: number;
  state: FreshnessState;
  formattedAge: string;
}

function getFreshnessState(ageMs: number): FreshnessState {
  if (ageMs >= CRITICAL_THRESHOLD_MS) return 'critical';
  if (ageMs >= STALE_THRESHOLD_MS) return 'stale';
  return 'fresh';
}

function formatRelativeTime(ageMs: number): string {
  const seconds = Math.floor(ageMs / 1000);
  if (seconds < 60) return 'just now';

  const minutes = Math.floor(seconds / 60);
  if (minutes === 1) return '1 minute ago';
  if (minutes < 60) return `${minutes} minutes ago`;

  const hours = Math.floor(minutes / 60);
  if (hours === 1) return '1 hour ago';
  if (hours < 24) return `${hours} hours ago`;

  const days = Math.floor(hours / 24);
  if (days === 1) return '1 day ago';
  return `${days} days ago`;
}

function formatCompact(ageMs: number): string {
  const seconds = Math.floor(ageMs / 1000);
  if (seconds < 60) return 'now';

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  return `${Math.floor(hours / 24)}d ago`;
}

function calculateAge(serverTimestamp: string, clientFetchTime: number): number {
  const serverTime = new Date(serverTimestamp).getTime();
  const now = Date.now();
  const age = now - serverTime;

  if (age < 0) {
    // Server timestamp is in the future — clock skew
    if (Math.abs(age) > MAX_CLOCK_SKEW_MS) {
      // Skew > 5 min — fall back to client fetch time
      return now - clientFetchTime;
    }
    return 0; // Small skew — treat as "just now"
  }

  return age;
}

export function useDataFreshness(lastUpdated: string | null): DataFreshnessResult {
  // Capture client time when lastUpdated changes (for clock skew fallback)
  const clientFetchTimeRef = useRef<number>(Date.now());

  const compute = useCallback((): DataFreshnessResult => {
    if (!lastUpdated) {
      return { ageMs: 0, state: 'loading', formattedAge: '' };
    }
    const ageMs = calculateAge(lastUpdated, clientFetchTimeRef.current);
    return {
      ageMs,
      state: getFreshnessState(ageMs),
      formattedAge: formatRelativeTime(ageMs),
    };
  }, [lastUpdated]);

  const [result, setResult] = useState<DataFreshnessResult>(compute);

  // Update client fetch time when lastUpdated changes
  useEffect(() => {
    if (lastUpdated) {
      clientFetchTimeRef.current = Date.now();
    }
    setResult(compute());
  }, [lastUpdated, compute]);

  // Update once per minute
  useEffect(() => {
    if (!lastUpdated) return;

    const interval = setInterval(() => {
      setResult(compute());
    }, 60_000);

    return () => clearInterval(interval);
  }, [lastUpdated, compute]);

  // Recalculate immediately on tab visibility change
  useEffect(() => {
    const handler = () => {
      if (document.visibilityState === 'visible') {
        setResult(compute());
      }
    };
    document.addEventListener('visibilitychange', handler);
    return () => document.removeEventListener('visibilitychange', handler);
  }, [compute]);

  return result;
}

// Export compact formatter for mobile use
export { formatCompact };
