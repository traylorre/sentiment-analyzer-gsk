'use client';

import { motion } from 'framer-motion';
import { Activity, Wifi, WifiOff } from 'lucide-react';
import { cn } from '@/lib/utils';

interface HeaderProps {
  title?: string;
  isConnected?: boolean;
  className?: string;
}

export function Header({
  title = 'Sentiment',
  isConnected = true,
  className,
}: HeaderProps) {
  return (
    <motion.header
      className={cn(
        'sticky top-0 z-40 w-full border-b border-border bg-background/80 backdrop-blur-lg',
        className
      )}
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
    >
      <div className="container flex h-14 items-center justify-between px-4">
        {/* Logo and title */}
        <div className="flex items-center gap-2">
          <motion.div
            className="flex items-center justify-center w-8 h-8 rounded-lg bg-accent/20"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <Activity className="h-5 w-5 text-accent" />
          </motion.div>
          <span className="font-semibold text-lg text-foreground">{title}</span>
        </div>

        {/* Connection status */}
        <div className="flex items-center gap-4">
          <motion.div
            className={cn(
              'flex items-center gap-1.5 text-sm',
              isConnected ? 'text-success' : 'text-destructive'
            )}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
          >
            {isConnected ? (
              <>
                <Wifi className="h-4 w-4" />
                <span className="hidden sm:inline">Live</span>
              </>
            ) : (
              <>
                <WifiOff className="h-4 w-4" />
                <span className="hidden sm:inline">Offline</span>
              </>
            )}
          </motion.div>
        </div>
      </div>
    </motion.header>
  );
}
