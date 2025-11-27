import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Plus, Trash2 } from 'lucide-react';
import {
  SwipeQuickActions,
  MoreActionsButton,
  COMMON_ACTIONS,
} from '@/components/navigation/quick-actions';

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
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

describe('SwipeQuickActions', () => {
  const mockAction1 = vi.fn();
  const mockAction2 = vi.fn();

  const actions = [
    { id: 'edit', label: 'Edit', icon: Plus, onClick: mockAction1 },
    { id: 'delete', label: 'Delete', icon: Trash2, onClick: mockAction2, variant: 'destructive' as const },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render all action buttons', () => {
    render(<SwipeQuickActions actions={actions} />);

    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(2);
  });

  it('should call onClick when action is clicked', () => {
    render(<SwipeQuickActions actions={actions} />);

    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[0]);

    expect(mockAction1).toHaveBeenCalled();
  });

  it('should apply destructive styling to destructive actions', () => {
    render(<SwipeQuickActions actions={actions} />);

    const buttons = screen.getAllByRole('button');
    const deleteButton = buttons[1];

    expect(deleteButton.className).toContain('bg-red-500');
  });
});

describe('MoreActionsButton', () => {
  const mockAction = vi.fn();

  const actions = [
    { id: 'test', label: 'Test Action', icon: Plus, onClick: mockAction },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render the more button', () => {
    render(<MoreActionsButton actions={actions} />);

    expect(screen.getByLabelText('More actions')).toBeInTheDocument();
  });

  it('should open action sheet when clicked', () => {
    render(<MoreActionsButton actions={actions} />);

    const button = screen.getByLabelText('More actions');
    fireEvent.click(button);

    expect(screen.getByText('Test Action')).toBeInTheDocument();
  });

  it('should show title in action sheet when provided', () => {
    render(<MoreActionsButton actions={actions} title="Select Action" />);

    const button = screen.getByLabelText('More actions');
    fireEvent.click(button);

    expect(screen.getByText('Select Action')).toBeInTheDocument();
  });
});

describe('COMMON_ACTIONS', () => {
  it('should create refresh action', () => {
    const onClick = vi.fn();
    const action = COMMON_ACTIONS.refresh(onClick);

    expect(action.id).toBe('refresh');
    expect(action.label).toBe('Refresh');

    action.onClick();
    expect(onClick).toHaveBeenCalled();
  });

  it('should create search action', () => {
    const onClick = vi.fn();
    const action = COMMON_ACTIONS.search(onClick);

    expect(action.id).toBe('search');
    expect(action.label).toBe('Search');
  });

  it('should create share action', () => {
    const onClick = vi.fn();
    const action = COMMON_ACTIONS.share(onClick);

    expect(action.id).toBe('share');
    expect(action.label).toBe('Share');
  });

  it('should create download action', () => {
    const onClick = vi.fn();
    const action = COMMON_ACTIONS.download(onClick);

    expect(action.id).toBe('download');
    expect(action.label).toBe('Download');
  });

  it('should create copy action', () => {
    const onClick = vi.fn();
    const action = COMMON_ACTIONS.copy(onClick);

    expect(action.id).toBe('copy');
    expect(action.label).toBe('Copy');
  });

  it('should create edit action', () => {
    const onClick = vi.fn();
    const action = COMMON_ACTIONS.edit(onClick);

    expect(action.id).toBe('edit');
    expect(action.label).toBe('Edit');
  });

  it('should create delete action with destructive variant', () => {
    const onClick = vi.fn();
    const action = COMMON_ACTIONS.delete(onClick);

    expect(action.id).toBe('delete');
    expect(action.label).toBe('Delete');
    expect(action.variant).toBe('destructive');
  });
});
