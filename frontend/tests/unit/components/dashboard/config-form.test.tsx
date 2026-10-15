import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ConfigForm } from '@/components/dashboard/config-form';
import type { Configuration } from '@/types/config';

vi.mock('@/components/dashboard/ticker-input', () => ({
  TickerSearch: () => null,
}));

const editing = (overrides: Partial<Configuration> = {}): Configuration => ({
  configId: 'c1',
  name: 'Tech',
  tickers: [{ symbol: 'AAPL', name: 'Apple', exchange: 'NASDAQ' }],
  timeframeDays: 30,
  includeExtendedHours: true,
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
  ...overrides,
});

function setup(props: Partial<React.ComponentProps<typeof ConfigForm>> = {}) {
  const all = { isOpen: true, onClose: vi.fn(), onSubmit: vi.fn(), ...props };
  const view = render(<ConfigForm {...all} />);
  const rerender = (next: Partial<React.ComponentProps<typeof ConfigForm>>) =>
    view.rerender(<ConfigForm {...all} {...next} />);
  return { rerender, nameInput: () => screen.getByPlaceholderText('My Watchlist') };
}

describe('ConfigForm', () => {
  it('opens empty in create mode', () => {
    const { nameInput } = setup();

    expect(nameInput()).toHaveValue('');
    expect(screen.getByText('0/5')).toBeInTheDocument();
  });

  it('opens populated in edit mode', () => {
    const { nameInput } = setup({ editingConfig: editing() });

    expect(nameInput()).toHaveValue('Tech');
    expect(screen.getByText('1/5')).toBeInTheDocument();
  });

  it('re-initializes when the configuration being edited changes', () => {
    const { nameInput, rerender } = setup({ editingConfig: editing() });

    rerender({ editingConfig: editing({ configId: 'c2', name: 'Energy', tickers: [] }) });

    expect(nameInput()).toHaveValue('Energy');
    expect(screen.getByText('0/5')).toBeInTheDocument();
  });

  it('resets user changes when closed and reopened', () => {
    const { nameInput, rerender } = setup();

    fireEvent.change(nameInput(), { target: { value: 'Draft' } });
    rerender({ isOpen: false });
    rerender({ isOpen: true });

    expect(nameInput()).toHaveValue('');
  });

  it('keeps user changes across a re-render with unchanged props', () => {
    const { nameInput, rerender } = setup();

    fireEvent.change(nameInput(), { target: { value: 'Draft' } });
    rerender({});

    expect(nameInput()).toHaveValue('Draft');
  });
});
