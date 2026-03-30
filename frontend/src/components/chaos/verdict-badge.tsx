import { cn } from '@/lib/utils';
import type { Verdict } from '@/types/chaos';

const VERDICT_STYLES: Record<Verdict, string> = {
  CLEAN: 'text-green-700 bg-green-500/10 dark:text-green-400',
  COMPROMISED: 'text-destructive bg-destructive/10',
  DRY_RUN_CLEAN: 'text-blue-700 bg-blue-500/10 dark:text-blue-400',
  RECOVERY_INCOMPLETE: 'text-amber-700 bg-amber-500/10 dark:text-amber-400',
  INCONCLUSIVE: 'text-muted-foreground bg-muted',
};

const VERDICT_LABELS: Record<Verdict, string> = {
  CLEAN: 'Clean',
  COMPROMISED: 'Compromised',
  DRY_RUN_CLEAN: 'Dry Run',
  RECOVERY_INCOMPLETE: 'Recovery Incomplete',
  INCONCLUSIVE: 'Inconclusive',
};

interface VerdictBadgeProps {
  verdict: Verdict;
  size?: 'sm' | 'md';
  className?: string;
}

export function VerdictBadge({ verdict, size = 'sm', className }: VerdictBadgeProps) {
  return (
    <span
      data-testid="verdict-badge"
      className={cn(
        'inline-flex items-center rounded-full font-medium',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm',
        VERDICT_STYLES[verdict] ?? VERDICT_STYLES.INCONCLUSIVE,
        className
      )}
    >
      {VERDICT_LABELS[verdict] ?? verdict}
    </span>
  );
}
