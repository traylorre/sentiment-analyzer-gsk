'use client';

import { cn } from '@/lib/utils';

interface SkipLinkProps {
  targetId: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * Skip link component for keyboard navigation accessibility.
 * Allows users to skip directly to main content.
 */
export function SkipLink({ targetId, children, className }: SkipLinkProps) {
  return (
    <a
      href={`#${targetId}`}
      className={cn(
        'sr-only focus:not-sr-only',
        'focus:fixed focus:top-4 focus:left-4 focus:z-50',
        'focus:px-4 focus:py-2 focus:rounded-lg',
        'focus:bg-accent focus:text-accent-foreground',
        'focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2',
        'font-medium text-sm',
        className
      )}
    >
      {children}
    </a>
  );
}

/**
 * Visually hidden text for screen readers.
 * Use for labels that should be announced but not displayed.
 */
interface VisuallyHiddenProps {
  children: React.ReactNode;
  as?: 'span' | 'div' | 'p' | 'label';
}

export function VisuallyHidden({ children, as: Component = 'span' }: VisuallyHiddenProps) {
  return <Component className="sr-only">{children}</Component>;
}

/**
 * Live region for announcing dynamic content changes to screen readers.
 */
interface LiveRegionProps {
  children: React.ReactNode;
  /** 'polite' waits for user to finish, 'assertive' interrupts immediately */
  politeness?: 'polite' | 'assertive';
  /** Set to true when content should be announced */
  atomic?: boolean;
  className?: string;
}

export function LiveRegion({
  children,
  politeness = 'polite',
  atomic = true,
  className,
}: LiveRegionProps) {
  return (
    <div
      role="status"
      aria-live={politeness}
      aria-atomic={atomic}
      className={cn('sr-only', className)}
    >
      {children}
    </div>
  );
}

/**
 * Focus trap helper - announces when focus is trapped in a modal/dialog.
 */
interface FocusTrapAnnouncementProps {
  isActive: boolean;
  label?: string;
}

export function FocusTrapAnnouncement({
  isActive,
  label = 'Dialog',
}: FocusTrapAnnouncementProps) {
  if (!isActive) return null;

  return (
    <LiveRegion politeness="assertive">
      {label} opened. Press Escape to close.
    </LiveRegion>
  );
}
