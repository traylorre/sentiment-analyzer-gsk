'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Clock, AlertTriangle } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface RateLimitMessageProps {
  retryAfterSeconds?: number;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function RateLimitMessage({
  retryAfterSeconds = 60,
  message = 'Too many requests',
  onRetry,
  className,
}: RateLimitMessageProps) {
  const [remainingSeconds, setRemainingSeconds] = useState(retryAfterSeconds);
  const [canRetry, setCanRetry] = useState(false);

  useEffect(() => {
    setRemainingSeconds(retryAfterSeconds);
    setCanRetry(false);

    if (retryAfterSeconds <= 0) {
      setCanRetry(true);
      return;
    }

    const interval = setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev <= 1) {
          setCanRetry(true);
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [retryAfterSeconds]);

  const formatTime = (seconds: number) => {
    if (seconds < 60) {
      return `${seconds}s`;
    }
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const progress = ((retryAfterSeconds - remainingSeconds) / retryAfterSeconds) * 100;

  return (
    <Card className={cn('p-4', className)}>
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-full bg-amber-500/10 flex items-center justify-center flex-shrink-0">
          <Clock className="w-6 h-6 text-amber-500" />
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-foreground mb-1">
            {message}
          </h3>
          <p className="text-sm text-muted-foreground mb-3">
            Please wait before trying again. This helps us keep the service running
            smoothly for everyone.
          </p>

          {/* Countdown */}
          {!canRetry && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Retry available in</span>
                <span className="font-mono font-medium text-amber-500">
                  {formatTime(remainingSeconds)}
                </span>
              </div>

              {/* Progress bar */}
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-amber-500"
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.5 }}
                />
              </div>
            </div>
          )}

          {/* Retry button */}
          {canRetry && onRetry && (
            <motion.button
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              onClick={onRetry}
              className="px-4 py-2 rounded-md bg-accent text-accent-foreground font-medium text-sm hover:bg-accent/90 transition-colors"
            >
              Try Again
            </motion.button>
          )}
        </div>
      </div>
    </Card>
  );
}

// Inline version for smaller spaces
interface RateLimitBannerProps {
  retryAfterSeconds?: number;
  className?: string;
}

export function RateLimitBanner({
  retryAfterSeconds = 60,
  className,
}: RateLimitBannerProps) {
  const [remainingSeconds, setRemainingSeconds] = useState(retryAfterSeconds);

  useEffect(() => {
    setRemainingSeconds(retryAfterSeconds);

    if (retryAfterSeconds <= 0) return;

    const interval = setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [retryAfterSeconds]);

  if (remainingSeconds <= 0) return null;

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded-md bg-amber-500/10 text-amber-500 text-sm',
        className
      )}
    >
      <AlertTriangle className="w-4 h-4 flex-shrink-0" />
      <span>Rate limited. Retry in {remainingSeconds}s</span>
    </div>
  );
}
