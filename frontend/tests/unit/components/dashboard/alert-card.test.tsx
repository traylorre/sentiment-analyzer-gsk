import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AlertCard, AlertCardCompact, AlertStatusBadge } from '@/components/dashboard/alert-card';
import type { AlertRule } from '@/types/alert';

// framer-motion is mocked globally in tests/setup.ts

const mockSentimentAlert: AlertRule = {
  alertId: 'alert-1',
  configId: 'config-1',
  ticker: 'AAPL',
  alertType: 'sentiment_threshold',
  thresholdValue: 0.75,
  thresholdDirection: 'above',
  isEnabled: true,
  lastTriggeredAt: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
  triggerCount: 5,
  createdAt: '2024-01-15T10:00:00Z',
};

const mockVolatilityAlert: AlertRule = {
  alertId: 'alert-2',
  configId: 'config-1',
  ticker: 'GOOGL',
  alertType: 'volatility_threshold',
  thresholdValue: 25.5,
  thresholdDirection: 'below',
  isEnabled: false,
  lastTriggeredAt: null,
  triggerCount: 0,
  createdAt: '2024-01-15T10:00:00Z',
};

describe('AlertCard', () => {
  it('should render ticker symbol', () => {
    render(<AlertCard alert={mockSentimentAlert} />);

    expect(screen.getByText('AAPL')).toBeInTheDocument();
  });

  it('should render sentiment alert type badge', () => {
    render(<AlertCard alert={mockSentimentAlert} />);

    expect(screen.getByText('Sentiment')).toBeInTheDocument();
  });

  it('should render volatility alert type badge', () => {
    render(<AlertCard alert={mockVolatilityAlert} />);

    expect(screen.getByText('Volatility')).toBeInTheDocument();
  });

  it('should render threshold value for sentiment', () => {
    render(<AlertCard alert={mockSentimentAlert} />);

    expect(screen.getByText('0.75')).toBeInTheDocument();
  });

  it('should render threshold value with percentage for volatility', () => {
    render(<AlertCard alert={mockVolatilityAlert} />);

    expect(screen.getByText('25.5%')).toBeInTheDocument();
  });

  it('should render direction text', () => {
    render(<AlertCard alert={mockSentimentAlert} />);

    expect(screen.getByText(/Alert when above/)).toBeInTheDocument();
  });

  it('should render trigger count', () => {
    render(<AlertCard alert={mockSentimentAlert} />);

    expect(screen.getByText('5 triggers')).toBeInTheDocument();
  });

  it('should render singular trigger text', () => {
    const singleTriggerAlert = { ...mockSentimentAlert, triggerCount: 1 };
    render(<AlertCard alert={singleTriggerAlert} />);

    expect(screen.getByText('1 trigger')).toBeInTheDocument();
  });

  it('should render last triggered time', () => {
    render(<AlertCard alert={mockSentimentAlert} />);

    expect(screen.getByText(/Last:/)).toBeInTheDocument();
  });

  it('should call onToggle when toggle switch clicked', () => {
    const onToggle = vi.fn();

    render(<AlertCard alert={mockSentimentAlert} onToggle={onToggle} />);

    const toggleSwitch = screen.getByRole('switch');
    fireEvent.click(toggleSwitch);

    expect(onToggle).toHaveBeenCalledWith('alert-1', false);
  });

  it('should call onToggle with true when enabling disabled alert', () => {
    const onToggle = vi.fn();

    render(<AlertCard alert={mockVolatilityAlert} onToggle={onToggle} />);

    const toggleSwitch = screen.getByRole('switch');
    fireEvent.click(toggleSwitch);

    expect(onToggle).toHaveBeenCalledWith('alert-2', true);
  });

  it('should call onEdit when edit button clicked', () => {
    const onEdit = vi.fn();

    render(<AlertCard alert={mockSentimentAlert} onEdit={onEdit} />);

    const editButton = screen.getByRole('button', { name: /edit/i });
    fireEvent.click(editButton);

    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it('should call onDelete when delete button clicked', () => {
    const onDelete = vi.fn();

    render(<AlertCard alert={mockSentimentAlert} onDelete={onDelete} />);

    // Find delete button by the trash icon
    const buttons = screen.getAllByRole('button');
    const deleteButton = buttons.find(b => b.querySelector('svg.lucide-trash-2'));

    if (deleteButton) {
      fireEvent.click(deleteButton);
    }

    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it('should show reduced opacity when alert is disabled', () => {
    const { container } = render(<AlertCard alert={mockVolatilityAlert} />);

    // Check for opacity-60 class on disabled card
    expect(container.querySelector('.opacity-60')).toBeInTheDocument();
  });
});

describe('AlertCardCompact', () => {
  it('should render ticker symbol', () => {
    render(<AlertCardCompact alert={mockSentimentAlert} />);

    expect(screen.getByText('AAPL')).toBeInTheDocument();
  });

  it('should render threshold value', () => {
    render(<AlertCardCompact alert={mockSentimentAlert} />);

    expect(screen.getByText('0.75')).toBeInTheDocument();
  });

  it('should call onClick when clicked', () => {
    const onClick = vi.fn();

    render(<AlertCardCompact alert={mockSentimentAlert} onClick={onClick} />);

    const card = screen.getByText('AAPL').closest('div');
    if (card) {
      fireEvent.click(card);
    }

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('should call onToggle when toggle switch clicked', () => {
    const onToggle = vi.fn();
    const onClick = vi.fn();

    render(<AlertCardCompact alert={mockSentimentAlert} onToggle={onToggle} onClick={onClick} />);

    const toggleSwitch = screen.getByRole('switch');
    fireEvent.click(toggleSwitch);

    expect(onToggle).toHaveBeenCalledWith('alert-1', false);
    // Should not trigger card click
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe('AlertStatusBadge', () => {
  it('should show Active for enabled alerts', () => {
    render(<AlertStatusBadge isEnabled={true} />);

    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('should show Paused for disabled alerts', () => {
    render(<AlertStatusBadge isEnabled={false} />);

    expect(screen.getByText('Paused')).toBeInTheDocument();
  });
});
