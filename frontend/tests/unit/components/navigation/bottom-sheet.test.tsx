import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BottomSheet, ActionSheet, useBottomSheet } from '@/components/navigation/bottom-sheet';
import { useViewStore } from '@/stores/view-store';

// framer-motion is mocked globally in tests/setup.ts

// Mock haptic hook
vi.mock('@/hooks/use-haptic', () => ({
  useHaptic: () => ({
    light: vi.fn(),
    medium: vi.fn(),
    heavy: vi.fn(),
  }),
}));

describe('BottomSheet', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useViewStore.getState().reset();
  });

  it('should not render when isOpen is false', () => {
    render(
      <BottomSheet isOpen={false} onClose={mockOnClose}>
        <div>Content</div>
      </BottomSheet>
    );

    expect(screen.queryByText('Content')).not.toBeInTheDocument();
  });

  it('should render when isOpen is true', () => {
    render(
      <BottomSheet isOpen={true} onClose={mockOnClose}>
        <div>Content</div>
      </BottomSheet>
    );

    expect(screen.getByText('Content')).toBeInTheDocument();
  });

  it('should render title when provided', () => {
    render(
      <BottomSheet isOpen={true} onClose={mockOnClose} title="Test Title">
        <div>Content</div>
      </BottomSheet>
    );

    expect(screen.getByText('Test Title')).toBeInTheDocument();
  });

  it('should call onClose when backdrop is clicked', () => {
    render(
      <BottomSheet isOpen={true} onClose={mockOnClose}>
        <div>Content</div>
      </BottomSheet>
    );

    // Click backdrop (first div with backdrop-blur class)
    const backdrop = document.querySelector('.backdrop-blur-sm');
    if (backdrop) {
      fireEvent.click(backdrop);
    }

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('should call onClose when close button is clicked', () => {
    render(
      <BottomSheet isOpen={true} onClose={mockOnClose} title="Test">
        <div>Content</div>
      </BottomSheet>
    );

    const closeButton = screen.getByLabelText('Close');
    fireEvent.click(closeButton);

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('should call onClose on escape key press', () => {
    render(
      <BottomSheet isOpen={true} onClose={mockOnClose}>
        <div>Content</div>
      </BottomSheet>
    );

    fireEvent.keyDown(document, { key: 'Escape' });

    expect(mockOnClose).toHaveBeenCalled();
  });
});

describe('ActionSheet', () => {
  const mockOnClose = vi.fn();
  const mockAction1 = vi.fn();
  const mockAction2 = vi.fn();

  const actions = [
    { label: 'Action 1', onClick: mockAction1 },
    { label: 'Action 2', onClick: mockAction2, variant: 'destructive' as const },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should not render when isOpen is false', () => {
    render(
      <ActionSheet isOpen={false} onClose={mockOnClose} actions={actions} />
    );

    expect(screen.queryByText('Action 1')).not.toBeInTheDocument();
  });

  it('should render all actions when open', () => {
    render(
      <ActionSheet isOpen={true} onClose={mockOnClose} actions={actions} />
    );

    expect(screen.getByText('Action 1')).toBeInTheDocument();
    expect(screen.getByText('Action 2')).toBeInTheDocument();
  });

  it('should render title when provided', () => {
    render(
      <ActionSheet isOpen={true} onClose={mockOnClose} actions={actions} title="Choose Action" />
    );

    expect(screen.getByText('Choose Action')).toBeInTheDocument();
  });

  it('should call action onClick and close when action is clicked', () => {
    render(
      <ActionSheet isOpen={true} onClose={mockOnClose} actions={actions} />
    );

    fireEvent.click(screen.getByText('Action 1'));

    expect(mockAction1).toHaveBeenCalled();
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('should render cancel button', () => {
    render(
      <ActionSheet isOpen={true} onClose={mockOnClose} actions={actions} />
    );

    expect(screen.getByText('Cancel')).toBeInTheDocument();
  });

  it('should call onClose when cancel is clicked', () => {
    render(
      <ActionSheet isOpen={true} onClose={mockOnClose} actions={actions} />
    );

    fireEvent.click(screen.getByText('Cancel'));

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('should render custom cancel label', () => {
    render(
      <ActionSheet
        isOpen={true}
        onClose={mockOnClose}
        actions={actions}
        cancelLabel="Dismiss"
      />
    );

    expect(screen.getByText('Dismiss')).toBeInTheDocument();
  });
});

describe('useBottomSheet', () => {
  beforeEach(() => {
    useViewStore.getState().reset();
  });

  it('should return bottom sheet state', () => {
    // Test the store state directly since hooks can't be called outside components
    const state = useViewStore.getState();

    expect(state.isBottomSheetOpen).toBe(false);
    expect(state.bottomSheetContent).toBeNull();
  });

  it('should open bottom sheet with content', () => {
    useViewStore.getState().openBottomSheet('test-content');

    const state = useViewStore.getState();
    expect(state.isBottomSheetOpen).toBe(true);
    expect(state.bottomSheetContent).toBe('test-content');
  });

  it('should close bottom sheet', () => {
    useViewStore.getState().openBottomSheet('test-content');
    useViewStore.getState().closeBottomSheet();

    const state = useViewStore.getState();
    expect(state.isBottomSheetOpen).toBe(false);
    expect(state.bottomSheetContent).toBeNull();
  });
});
