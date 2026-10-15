import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { DataFreshnessIndicator } from '@/components/dashboard/data-freshness-indicator';

const T0 = new Date('2026-10-14T12:00:00Z').getTime();
const MINUTE = 60_000;
// Stale at 2x and critical at 4x the 5-minute refresh interval
const iso = (ms: number) => new Date(ms).toISOString();

const indicator = () => screen.getByTestId('data-freshness-indicator');
const announcement = () => indicator().querySelector('[aria-live="polite"]')!.textContent;

describe('DataFreshnessIndicator', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(T0);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders nothing while there is no timestamp', () => {
    const { container } = render(<DataFreshnessIndicator lastUpdated={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows fresh data without an announcement', () => {
    render(<DataFreshnessIndicator lastUpdated={iso(T0 - 2 * MINUTE)} />);

    expect(indicator()).toHaveAttribute('data-freshness-state', 'fresh');
    expect(screen.getByText('Last updated 2 minutes ago')).toBeInTheDocument();
    expect(announcement()).toBe('');
  });

  it('ages on the minute tick and announces the stale transition in the same render', () => {
    render(<DataFreshnessIndicator lastUpdated={iso(T0 - 9 * MINUTE)} />);
    expect(indicator()).toHaveAttribute('data-freshness-state', 'fresh');

    act(() => {
      vi.advanceTimersByTime(MINUTE);
    });

    expect(indicator()).toHaveAttribute('data-freshness-state', 'stale');
    expect(screen.getByText('Last updated 10 minutes ago')).toBeInTheDocument();
    expect(announcement()).toBe('Data may be outdated');
  });

  it('announces recovery when new data arrives', () => {
    const { rerender } = render(<DataFreshnessIndicator lastUpdated={iso(T0 - 25 * MINUTE)} />);
    expect(indicator()).toHaveAttribute('data-freshness-state', 'critical');

    rerender(<DataFreshnessIndicator lastUpdated={iso(T0)} />);

    expect(indicator()).toHaveAttribute('data-freshness-state', 'fresh');
    expect(announcement()).toBe('Data connection restored');
  });

  it('measures from the client fetch time when the server clock is far ahead', () => {
    render(<DataFreshnessIndicator lastUpdated={iso(T0 + 30 * MINUTE)} />);
    expect(screen.getByText('Last updated just now')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(3 * MINUTE);
    });

    expect(screen.getByText('Last updated 3 minutes ago')).toBeInTheDocument();
  });

  it('recalculates when the tab becomes visible', () => {
    render(<DataFreshnessIndicator lastUpdated={iso(T0 - 2 * MINUTE)} />);

    vi.setSystemTime(T0 + 20 * MINUTE);
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    expect(indicator()).toHaveAttribute('data-freshness-state', 'critical');
  });
});
