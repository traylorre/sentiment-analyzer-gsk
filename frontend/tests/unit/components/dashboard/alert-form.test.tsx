import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AlertForm } from '@/components/dashboard/alert-form';
import type { AlertRule } from '@/types/alert';
import type { Configuration } from '@/types/config';

const config = (configId: string, symbols: string[]): Configuration => ({
  configId,
  name: `Config ${configId}`,
  tickers: symbols.map((symbol) => ({ symbol, name: symbol, exchange: 'NASDAQ' })),
  timeframeDays: 7,
  includeExtendedHours: false,
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
});

const configurations = [config('c1', ['AAPL', 'MSFT']), config('c2', ['TSLA'])];

const alert = (overrides: Partial<AlertRule> = {}): AlertRule => ({
  alertId: 'a1',
  configId: 'c2',
  ticker: 'TSLA',
  alertType: 'volatility_threshold',
  thresholdValue: 12.5,
  thresholdDirection: 'below',
  isEnabled: true,
  lastTriggeredAt: null,
  triggerCount: 0,
  createdAt: '2026-01-01T00:00:00Z',
  ...overrides,
});

function setup(props: Partial<React.ComponentProps<typeof AlertForm>> = {}) {
  const onSubmit = vi.fn();
  const all = {
    isOpen: true,
    configurations,
    onClose: vi.fn(),
    onSubmit,
    ...props,
  };
  const view = render(<AlertForm {...all} />);
  const rerender = (next: Partial<React.ComponentProps<typeof AlertForm>>) =>
    view.rerender(<AlertForm {...all} {...next} />);
  const submit = () => fireEvent.submit(screen.getByRole('combobox').closest('form')!);
  return { onSubmit, rerender, submit };
}

const DEFAULTS = { alertType: 'sentiment_threshold', thresholdValue: 0.5, thresholdDirection: 'above' };

describe('AlertForm', () => {
  it('opens in create mode on the first configuration and its first ticker', () => {
    const { onSubmit, submit } = setup();

    submit();

    expect(onSubmit).toHaveBeenCalledWith({ configId: 'c1', ticker: 'AAPL', ...DEFAULTS });
  });

  it('switches to the first ticker of a newly chosen configuration', () => {
    const { onSubmit, submit } = setup();

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'c2' } });
    submit();

    expect(onSubmit).toHaveBeenCalledWith({ configId: 'c2', ticker: 'TSLA', ...DEFAULTS });
  });

  it('keeps a ticker the user picked', () => {
    const { onSubmit, submit } = setup();

    fireEvent.click(screen.getByRole('button', { name: 'MSFT' }));
    submit();

    expect(onSubmit).toHaveBeenCalledWith({ configId: 'c1', ticker: 'MSFT', ...DEFAULTS });
  });

  it('opens in edit mode with the alert being edited', () => {
    const { onSubmit, submit } = setup({ editingAlert: alert() });

    submit();

    expect(onSubmit).toHaveBeenCalledWith({
      configId: 'c2',
      ticker: 'TSLA',
      alertType: 'volatility_threshold',
      thresholdValue: 12.5,
      thresholdDirection: 'below',
    });
  });

  it('re-initializes when the alert being edited changes', () => {
    const { onSubmit, rerender, submit } = setup({ editingAlert: alert() });

    rerender({ editingAlert: alert({ alertId: 'a2', configId: 'c1', ticker: 'MSFT' }) });
    submit();

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ configId: 'c1', ticker: 'MSFT' })
    );
  });

  it('resets user changes when closed and reopened', () => {
    const { onSubmit, rerender, submit } = setup();

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'c2' } });
    rerender({ isOpen: false });
    rerender({ isOpen: true });
    submit();

    expect(onSubmit).toHaveBeenCalledWith({ configId: 'c1', ticker: 'AAPL', ...DEFAULTS });
  });

  it('keeps user changes across a re-render with unchanged props', () => {
    const { onSubmit, rerender, submit } = setup();

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'c2' } });
    rerender({});
    submit();

    expect(onSubmit).toHaveBeenCalledWith({ configId: 'c2', ticker: 'TSLA', ...DEFAULTS });
  });
});
