'use client';

import { motion, AnimatePresence, type Variants } from 'framer-motion';
import { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface GlowPulseProps {
  children: ReactNode;
  isActive: boolean;
  className?: string;
  glowColor?: string;
  duration?: number;
}

const glowVariants: Variants = {
  initial: {
    boxShadow: '0 0 0 0 rgba(0, 255, 255, 0)',
  },
  glow: {
    boxShadow: [
      '0 0 0 0 rgba(0, 255, 255, 0)',
      '0 0 8px 2px rgba(0, 255, 255, 0.4)',
      '0 0 16px 4px rgba(0, 255, 255, 0.3)',
      '0 0 8px 2px rgba(0, 255, 255, 0.2)',
      '0 0 0 0 rgba(0, 255, 255, 0)',
    ],
    transition: {
      duration: 1.5,
      ease: 'easeInOut',
    },
  },
};

export function GlowPulse({
  children,
  isActive,
  className,
  glowColor = 'rgba(0, 255, 255, 0.4)',
  duration = 1.5,
}: GlowPulseProps) {
  return (
    <motion.div
      className={cn('relative rounded-md', className)}
      variants={glowVariants}
      initial="initial"
      animate={isActive ? 'glow' : 'initial'}
      style={
        {
          '--glow-color': glowColor,
        } as React.CSSProperties
      }
    >
      {children}

      {/* Overlay glow effect */}
      <AnimatePresence>
        {isActive && (
          <motion.div
            className="absolute inset-0 rounded-md pointer-events-none"
            initial={{ opacity: 0 }}
            animate={{
              opacity: [0, 0.3, 0],
            }}
            exit={{ opacity: 0 }}
            transition={{ duration, ease: 'easeInOut' }}
            style={{
              background: `radial-gradient(circle at center, ${glowColor} 0%, transparent 70%)`,
            }}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// Value change animation with number transition
interface AnimatedUpdateProps {
  value: number | string;
  previousValue?: number | string;
  isUpdated: boolean;
  className?: string;
  formatFn?: (value: number | string) => string;
}

export function AnimatedUpdate({
  value,
  previousValue,
  isUpdated,
  className,
  formatFn = String,
}: AnimatedUpdateProps) {
  const formattedValue = formatFn(value);
  const hasChanged = previousValue !== undefined && value !== previousValue;

  return (
    <GlowPulse isActive={isUpdated} className={className}>
      <motion.span
        key={formattedValue}
        initial={hasChanged ? { opacity: 0, y: -10 } : false}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="inline-block"
      >
        {formattedValue}
      </motion.span>
    </GlowPulse>
  );
}

// Pulse ring animation
interface PulseRingProps {
  isActive: boolean;
  className?: string;
  color?: string;
  size?: 'sm' | 'md' | 'lg';
}

const sizeClasses = {
  sm: 'w-2 h-2',
  md: 'w-3 h-3',
  lg: 'w-4 h-4',
};

export function PulseRing({
  isActive,
  className,
  color = 'bg-accent',
  size = 'md',
}: PulseRingProps) {
  return (
    <div className={cn('relative', sizeClasses[size], className)}>
      {/* Outer pulse ring */}
      <AnimatePresence>
        {isActive && (
          <motion.div
            className={cn('absolute inset-0 rounded-full', color)}
            initial={{ opacity: 0.6, scale: 1 }}
            animate={{ opacity: 0, scale: 2.5 }}
            exit={{ opacity: 0 }}
            transition={{
              duration: 1,
              repeat: Infinity,
              ease: 'easeOut',
            }}
          />
        )}
      </AnimatePresence>

      {/* Inner dot */}
      <div className={cn('absolute inset-0 rounded-full', color)} />
    </div>
  );
}

// Shimmer effect for loading states
interface ShimmerProps {
  children: ReactNode;
  isActive: boolean;
  className?: string;
}

export function Shimmer({ children, isActive, className }: ShimmerProps) {
  return (
    <div className={cn('relative overflow-hidden', className)}>
      {children}

      <AnimatePresence>
        {isActive && (
          <motion.div
            className="absolute inset-0 pointer-events-none"
            initial={{ x: '-100%' }}
            animate={{ x: '100%' }}
            exit={{ opacity: 0 }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
            style={{
              background:
                'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.1) 50%, transparent 100%)',
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

// Highlight flash for new data
interface FlashHighlightProps {
  children: ReactNode;
  isActive: boolean;
  className?: string;
  color?: string;
}

export function FlashHighlight({
  children,
  isActive,
  className,
  color = 'bg-accent/20',
}: FlashHighlightProps) {
  return (
    <motion.div
      className={cn('relative', className)}
      animate={
        isActive
          ? {
              backgroundColor: [
                'transparent',
                'rgba(0, 255, 255, 0.2)',
                'transparent',
              ],
            }
          : {}
      }
      transition={{ duration: 1, ease: 'easeInOut' }}
    >
      {children}
    </motion.div>
  );
}
