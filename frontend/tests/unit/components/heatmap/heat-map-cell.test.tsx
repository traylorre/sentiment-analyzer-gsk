import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  HeatMapCell,
  HeatMapCellSkeleton,
  HeatMapEmptyCell,
} from '@/components/heatmap/heat-map-cell';
import { useChartStore } from '@/stores/chart-store';
import type { HeatMapCell as HeatMapCellType } from '@/types/heatmap';

// framer-motion is mocked globally in tests/setup.ts

// Mock haptic hook
vi.mock('@/hooks/use-haptic', () => ({
  useHaptic: () => ({
    light: vi.fn(),
    medium: vi.fn(),
    heavy: vi.fn(),
  }),
}));

describe('HeatMapCell', () => {
  const mockCell: HeatMapCellType = {
    source: 'tiingo',
    score: 0.75,
    color: '#22C55E',
  };

  beforeEach(() => {
    useChartStore.getState().setHoveredCell(null);
  });

  it('should render score value', () => {
    render(<HeatMapCell data={mockCell} ticker="AAPL" />);

    expect(screen.getByText('+0.75')).toBeInTheDocument();
  });

  it('should hide value when showValue is false', () => {
    render(<HeatMapCell data={mockCell} ticker="AAPL" showValue={false} />);

    expect(screen.queryByText('+0.75')).not.toBeInTheDocument();
  });

  it('should call onClick when clicked', () => {
    const onClick = vi.fn();
    render(<HeatMapCell data={mockCell} ticker="AAPL" onClick={onClick} />);

    fireEvent.click(screen.getByRole('gridcell'));

    expect(onClick).toHaveBeenCalled();
  });

  it('should call onHover when mouse enters', () => {
    const onHover = vi.fn();
    render(<HeatMapCell data={mockCell} ticker="AAPL" onHover={onHover} />);

    fireEvent.mouseEnter(screen.getByRole('gridcell'));

    expect(onHover).toHaveBeenCalledWith(mockCell);
  });

  it('should call onHover with null when mouse leaves', () => {
    const onHover = vi.fn();
    render(<HeatMapCell data={mockCell} ticker="AAPL" onHover={onHover} />);

    fireEvent.mouseEnter(screen.getByRole('gridcell'));
    fireEvent.mouseLeave(screen.getByRole('gridcell'));

    expect(onHover).toHaveBeenLastCalledWith(null);
  });

  it('should update chart store hovered cell on hover', () => {
    render(<HeatMapCell data={mockCell} ticker="AAPL" />);

    fireEvent.mouseEnter(screen.getByRole('gridcell'));

    const state = useChartStore.getState();
    // source value can be the source name or period name
    expect(state.hoveredCell).toEqual({ ticker: 'AAPL', source: 'tiingo' });
  });

  it('should have proper accessibility attributes', () => {
    render(<HeatMapCell data={mockCell} ticker="AAPL" />);

    const cell = screen.getByRole('gridcell');
    expect(cell).toHaveAttribute('aria-label');
    expect(cell).toHaveAttribute('tabindex', '0');
  });

  it('should apply size classes', () => {
    const { container, rerender } = render(
      <HeatMapCell data={mockCell} ticker="AAPL" size="sm" />
    );
    expect(container.firstChild).toHaveClass('w-10', 'h-10');

    rerender(<HeatMapCell data={mockCell} ticker="AAPL" size="lg" />);
    expect(container.firstChild).toHaveClass('w-20', 'h-20');
  });

  it('should apply hover styles when isHovered', () => {
    const { container } = render(
      <HeatMapCell data={mockCell} ticker="AAPL" isHovered />
    );

    expect(container.firstChild).toHaveClass('ring-2');
  });
});

describe('HeatMapCellSkeleton', () => {
  it('should render skeleton', () => {
    const { container } = render(<HeatMapCellSkeleton />);

    expect(container.firstChild).toHaveClass('animate-pulse');
  });

  it('should apply size classes', () => {
    const { container, rerender } = render(<HeatMapCellSkeleton size="sm" />);
    expect(container.firstChild).toHaveClass('w-10', 'h-10');

    rerender(<HeatMapCellSkeleton size="lg" />);
    expect(container.firstChild).toHaveClass('w-20', 'h-20');
  });
});

describe('HeatMapEmptyCell', () => {
  it('should render N/A text', () => {
    render(<HeatMapEmptyCell />);

    expect(screen.getByText('N/A')).toBeInTheDocument();
  });

  it('should apply size classes', () => {
    const { container, rerender } = render(<HeatMapEmptyCell size="sm" />);
    expect(container.firstChild).toHaveClass('w-10', 'h-10');

    rerender(<HeatMapEmptyCell size="lg" />);
    expect(container.firstChild).toHaveClass('w-20', 'h-20');
  });
});
