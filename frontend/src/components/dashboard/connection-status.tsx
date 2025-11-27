'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { Wifi, WifiOff, Loader2 } from 'lucide-react';
import type { SSEStatus } from '@/lib/api/sse';
import { cn } from '@/lib/utils';

interface ConnectionStatusProps {
  status: SSEStatus;
  className?: string;
  showLabel?: boolean;
}

const statusConfig: Record<
  SSEStatus,
  {
    icon: typeof Wifi;
    label: string;
    color: string;
    bgColor: string;
    pulseColor?: string;
  }
> = {
  connected: {
    icon: Wifi,
    label: 'Live',
    color: 'text-green-500',
    bgColor: 'bg-green-500/10',
    pulseColor: 'bg-green-500',
  },
  connecting: {
    icon: Loader2,
    label: 'Connecting',
    color: 'text-amber-500',
    bgColor: 'bg-amber-500/10',
  },
  disconnected: {
    icon: WifiOff,
    label: 'Offline',
    color: 'text-muted-foreground',
    bgColor: 'bg-muted/20',
  },
  error: {
    icon: WifiOff,
    label: 'Error',
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
  },
};

export function ConnectionStatus({
  status,
  className,
  showLabel = true,
}: ConnectionStatusProps) {
  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        'flex items-center gap-1.5 px-2 py-1 rounded-full',
        config.bgColor,
        className
      )}
    >
      <div className="relative flex items-center justify-center">
        {/* Pulse animation for connected status */}
        {status === 'connected' && config.pulseColor && (
          <motion.div
            className={cn('absolute inset-0 rounded-full', config.pulseColor)}
            initial={{ opacity: 0.6, scale: 1 }}
            animate={{ opacity: 0, scale: 2 }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              ease: 'easeOut',
            }}
          />
        )}

        {/* Icon */}
        <motion.div
          animate={status === 'connecting' ? { rotate: 360 } : { rotate: 0 }}
          transition={
            status === 'connecting'
              ? { duration: 1, repeat: Infinity, ease: 'linear' }
              : { duration: 0 }
          }
        >
          <Icon className={cn('w-3.5 h-3.5 relative z-10', config.color)} />
        </motion.div>
      </div>

      {showLabel && (
        <span className={cn('text-xs font-medium', config.color)}>
          {config.label}
        </span>
      )}
    </div>
  );
}

// Inline dot indicator (minimal version)
interface ConnectionDotProps {
  status: SSEStatus;
  className?: string;
}

export function ConnectionDot({ status, className }: ConnectionDotProps) {
  const colorMap: Record<SSEStatus, string> = {
    connected: 'bg-green-500',
    connecting: 'bg-amber-500',
    disconnected: 'bg-muted-foreground',
    error: 'bg-red-500',
  };

  return (
    <div className={cn('relative', className)}>
      {/* Pulse for connected */}
      <AnimatePresence>
        {status === 'connected' && (
          <motion.div
            className={cn('absolute inset-0 rounded-full', colorMap[status])}
            initial={{ opacity: 0.6, scale: 1 }}
            animate={{ opacity: 0, scale: 2 }}
            exit={{ opacity: 0 }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              ease: 'easeOut',
            }}
          />
        )}
      </AnimatePresence>

      {/* Solid dot */}
      <motion.div
        className={cn('w-2 h-2 rounded-full relative z-10', colorMap[status])}
        animate={status === 'connecting' ? { opacity: [1, 0.5, 1] } : { opacity: 1 }}
        transition={
          status === 'connecting'
            ? { duration: 1, repeat: Infinity, ease: 'easeInOut' }
            : { duration: 0 }
        }
      />
    </div>
  );
}

// Toast notification for connection status changes
interface ConnectionToastProps {
  status: SSEStatus;
  show: boolean;
  onClose?: () => void;
}

export function ConnectionToast({ status, show, onClose }: ConnectionToastProps) {
  const config = statusConfig[status];

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className={cn(
            'fixed bottom-4 right-4 z-50',
            'flex items-center gap-2 px-4 py-2 rounded-lg',
            'bg-background border border-border shadow-lg',
            config.bgColor
          )}
          initial={{ opacity: 0, y: 20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.2 }}
        >
          <config.icon className={cn('w-4 h-4', config.color)} />
          <span className="text-sm text-foreground">
            {status === 'connected' && 'Connected to live updates'}
            {status === 'connecting' && 'Connecting...'}
            {status === 'disconnected' && 'Disconnected from live updates'}
            {status === 'error' && 'Connection error'}
          </span>
          {onClose && (
            <button
              onClick={onClose}
              className="ml-2 text-muted-foreground hover:text-foreground"
            >
              &times;
            </button>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
