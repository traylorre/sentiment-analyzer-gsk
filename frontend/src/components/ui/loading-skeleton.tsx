import { cn } from '@/lib/utils';
import { Skeleton } from './skeleton';

interface LoadingSkeletonProps {
  className?: string;
  variant?: 'card' | 'chart' | 'list' | 'text';
}

export function LoadingSkeleton({ className, variant = 'card' }: LoadingSkeletonProps) {
  switch (variant) {
    case 'chart':
      return (
        <div className={cn('space-y-3', className)}>
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-[300px] w-full rounded-lg" />
          <div className="flex justify-between">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-16" />
          </div>
        </div>
      );

    case 'list':
      return (
        <div className={cn('space-y-4', className)}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <Skeleton className="h-12 w-12 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            </div>
          ))}
        </div>
      );

    case 'text':
      return (
        <div className={cn('space-y-2', className)}>
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-4/5" />
          <Skeleton className="h-4 w-3/5" />
        </div>
      );

    case 'card':
    default:
      return (
        <div className={cn('rounded-lg border border-border bg-card p-6 space-y-4', className)}>
          <div className="flex items-center justify-between">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-8 w-8 rounded-full" />
          </div>
          <Skeleton className="h-24 w-full" />
          <div className="flex gap-2">
            <Skeleton className="h-6 w-16 rounded-full" />
            <Skeleton className="h-6 w-16 rounded-full" />
          </div>
        </div>
      );
  }
}

export function ChartSkeleton({ className }: { className?: string }) {
  return <LoadingSkeleton variant="chart" className={className} />;
}

export function CardSkeleton({ className }: { className?: string }) {
  return <LoadingSkeleton variant="card" className={className} />;
}
