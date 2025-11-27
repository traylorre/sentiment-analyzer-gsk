'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { getSentimentColor, formatSentimentScore } from '@/lib/utils';

interface ChartCrosshairProps {
  visible: boolean;
  x: number;           // Position as percentage (0-100)
  value: number;       // Sentiment value
  timestamp?: string;
  className?: string;
}

export function ChartCrosshair({
  visible,
  x,
  value,
  timestamp,
  className,
}: ChartCrosshairProps) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className={cn('absolute top-0 bottom-0 pointer-events-none', className)}
          style={{ left: `${x}%` }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.1 }}
        >
          {/* Vertical line */}
          <div className="absolute top-0 bottom-0 w-px bg-accent" />

          {/* Glowing dot */}
          <motion.div
            className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2"
            animate={{
              boxShadow: [
                '0 0 5px rgba(0, 255, 255, 0.5)',
                '0 0 15px rgba(0, 255, 255, 0.8)',
                '0 0 5px rgba(0, 255, 255, 0.5)',
              ],
            }}
            transition={{
              duration: 1,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          >
            <div
              className="w-4 h-4 rounded-full border-2"
              style={{
                backgroundColor: getSentimentColor(value),
                borderColor: '#0a0a0a',
              }}
            />
          </motion.div>

          {/* Value tooltip */}
          <motion.div
            className="absolute -top-8 -translate-x-1/2 px-2 py-1 rounded bg-card border border-accent/30 text-sm font-medium"
            initial={{ y: 10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.15 }}
          >
            <span style={{ color: getSentimentColor(value) }}>
              {formatSentimentScore(value)}
            </span>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
