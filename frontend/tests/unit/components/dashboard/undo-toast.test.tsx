import { forwardRef, type ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { UndoToast } from '@/components/dashboard/delete-confirmation';

// Expose the progress bar's animation target, which the shared motion mock drops
vi.mock('framer-motion', () => {
  const div = forwardRef<HTMLDivElement, { children?: ReactNode; className?: string; animate?: { width?: string } }>(
    ({ children, className, animate }, ref) => (
      <div ref={ref} className={className} data-width={animate?.width}>
        {children}
      </div>
    )
  );
  div.displayName = 'motion.div';
  return {
    motion: { div },
    AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
  };
});

const width = () => Number.parseFloat(document.querySelector('.bg-accent')!.getAttribute('data-width')!);

describe('UndoToast', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const props = { message: 'Deleted', onUndo: vi.fn(), duration: 5000 };

  it('drains the progress bar and dismisses after the duration', () => {
    const onDismiss = vi.fn();
    render(<UndoToast {...props} isVisible onDismiss={onDismiss} />);
    expect(screen.getByText('Deleted')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(2500);
    });
    expect(width()).toBeCloseTo(50, 0);
    expect(onDismiss).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(2550);
    });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('starts full again when shown after being hidden', () => {
    const onDismiss = vi.fn();
    const { rerender } = render(<UndoToast {...props} isVisible onDismiss={onDismiss} />);
    act(() => {
      vi.advanceTimersByTime(2500);
    });

    rerender(<UndoToast {...props} isVisible={false} onDismiss={onDismiss} />);
    rerender(<UndoToast {...props} isVisible onDismiss={onDismiss} />);

    expect(width()).toBe(100);
  });
});
