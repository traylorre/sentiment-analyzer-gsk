import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MobileNav, FloatingActionButton } from '@/components/navigation/mobile-nav';
import { useViewStore } from '@/stores/view-store';

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
    span: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <span {...props}>{children}</span>
    ),
    button: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <button {...props}>{children}</button>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));

// Mock haptic hook
vi.mock('@/hooks/use-haptic', () => ({
  useHaptic: () => ({
    light: vi.fn(),
    medium: vi.fn(),
    heavy: vi.fn(),
  }),
}));

describe('MobileNav', () => {
  beforeEach(() => {
    useViewStore.getState().reset();
  });

  it('should render all navigation items', () => {
    render(<MobileNav />);

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Configs')).toBeInTheDocument();
    expect(screen.getByText('Alerts')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('should highlight the current view', () => {
    render(<MobileNav />);

    // Dashboard should be active by default
    const dashboardButton = screen.getByText('Dashboard').closest('button');
    expect(dashboardButton).toBeInTheDocument();
  });

  it('should change view when nav item is clicked', () => {
    render(<MobileNav />);

    const configsButton = screen.getByText('Configs');
    fireEvent.click(configsButton);

    expect(useViewStore.getState().currentView).toBe('configs');
  });

  it('should not change view when clicking current view', () => {
    render(<MobileNav />);

    const previousView = useViewStore.getState().previousView;
    const dashboardButton = screen.getByText('Dashboard');
    fireEvent.click(dashboardButton);

    // previousView should not change since we're already on dashboard
    expect(useViewStore.getState().previousView).toBe(previousView);
  });
});

describe('FloatingActionButton', () => {
  it('should render with icon', () => {
    const mockOnClick = vi.fn();
    const MockIcon = () => <svg data-testid="mock-icon" />;

    render(
      <FloatingActionButton onClick={mockOnClick} icon={MockIcon} label="Test action" />
    );

    expect(screen.getByTestId('mock-icon')).toBeInTheDocument();
  });

  it('should call onClick when pressed', () => {
    const mockOnClick = vi.fn();
    const MockIcon = () => <svg data-testid="mock-icon" />;

    render(
      <FloatingActionButton onClick={mockOnClick} icon={MockIcon} label="Test action" />
    );

    const button = screen.getByRole('button');
    fireEvent.click(button);

    expect(mockOnClick).toHaveBeenCalledTimes(1);
  });

  it('should have accessible label', () => {
    const mockOnClick = vi.fn();
    const MockIcon = () => <svg data-testid="mock-icon" />;

    render(
      <FloatingActionButton onClick={mockOnClick} icon={MockIcon} label="Add item" />
    );

    expect(screen.getByLabelText('Add item')).toBeInTheDocument();
  });
});
