'use client';

import { useEffect, useState, useRef } from 'react';
import { motion, useSpring, useMotionValue, animate } from 'framer-motion';
import { cn, getSentimentColor, formatSentimentScore } from '@/lib/utils';

interface AnimatedValueProps {
  value: number;
  format?: (value: number) => string;
  className?: string;
  duration?: number;
}

export function AnimatedValue({
  value,
  format = (v) => v.toFixed(2),
  className,
  duration = 0.5,
}: AnimatedValueProps) {
  const [displayValue, setDisplayValue] = useState(value);
  const prevValue = useRef(value);

  useEffect(() => {
    const controls = animate(prevValue.current, value, {
      duration,
      onUpdate: (latest) => setDisplayValue(latest),
    });

    prevValue.current = value;

    return () => controls.stop();
  }, [value, duration]);

  return <span className={className}>{format(displayValue)}</span>;
}

// Animated sentiment score with color transition
interface AnimatedSentimentScoreProps {
  score: number;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showLabel?: boolean;
  className?: string;
}

export function AnimatedSentimentScore({
  score,
  size = 'md',
  showLabel = false,
  className,
}: AnimatedSentimentScoreProps) {
  const [displayScore, setDisplayScore] = useState(score);
  const [displayColor, setDisplayColor] = useState(getSentimentColor(score));
  const prevScore = useRef(score);

  useEffect(() => {
    const controls = animate(prevScore.current, score, {
      duration: 0.5,
      onUpdate: (latest) => {
        setDisplayScore(latest);
        setDisplayColor(getSentimentColor(latest));
      },
    });

    prevScore.current = score;

    return () => controls.stop();
  }, [score]);

  const sizeStyles = {
    sm: 'text-lg',
    md: 'text-2xl',
    lg: 'text-4xl',
    xl: 'text-6xl',
  };

  return (
    <motion.div
      className={cn('font-bold tabular-nums', sizeStyles[size], className)}
      style={{ color: displayColor }}
      animate={{ scale: [1, 1.05, 1] }}
      transition={{ duration: 0.3 }}
      key={Math.round(score * 100)} // Re-animate on significant change
    >
      {formatSentimentScore(displayScore)}
      {showLabel && (
        <span className="text-sm font-normal text-muted-foreground ml-2">
          {displayScore >= 0.3 ? 'Bullish' : displayScore <= -0.3 ? 'Bearish' : 'Neutral'}
        </span>
      )}
    </motion.div>
  );
}

// Animated counter for integers
interface AnimatedCounterProps {
  value: number;
  className?: string;
  duration?: number;
  prefix?: string;
  suffix?: string;
}

export function AnimatedCounter({
  value,
  className,
  duration = 0.5,
  prefix = '',
  suffix = '',
}: AnimatedCounterProps) {
  const [displayValue, setDisplayValue] = useState(value);
  const prevValue = useRef(value);

  useEffect(() => {
    const controls = animate(prevValue.current, value, {
      duration,
      onUpdate: (latest) => setDisplayValue(Math.round(latest)),
    });

    prevValue.current = value;

    return () => controls.stop();
  }, [value, duration]);

  return (
    <span className={cn('tabular-nums', className)}>
      {prefix}
      {displayValue.toLocaleString()}
      {suffix}
    </span>
  );
}

// Animated percentage
interface AnimatedPercentageProps {
  value: number; // 0-1 or 0-100
  isPercentage?: boolean; // If true, value is already 0-100
  decimals?: number;
  className?: string;
  showSign?: boolean;
}

export function AnimatedPercentage({
  value,
  isPercentage = false,
  decimals = 1,
  className,
  showSign = false,
}: AnimatedPercentageProps) {
  const displayValue = isPercentage ? value : value * 100;
  const sign = showSign && displayValue > 0 ? '+' : '';

  return (
    <AnimatedValue
      value={displayValue}
      format={(v) => `${sign}${v.toFixed(decimals)}%`}
      className={className}
    />
  );
}

// Spring-based animated number with bounce effect
interface SpringValueProps {
  value: number;
  format?: (value: number) => string;
  className?: string;
  stiffness?: number;
  damping?: number;
}

export function SpringValue({
  value,
  format = (v) => v.toFixed(2),
  className,
  stiffness = 300,
  damping = 30,
}: SpringValueProps) {
  const motionValue = useMotionValue(value);
  const springValue = useSpring(motionValue, { stiffness, damping });
  const [displayValue, setDisplayValue] = useState(value);

  useEffect(() => {
    motionValue.set(value);
  }, [value, motionValue]);

  useEffect(() => {
    return springValue.on('change', (latest) => {
      setDisplayValue(latest);
    });
  }, [springValue]);

  return <span className={className}>{format(displayValue)}</span>;
}

// Animated progress bar
interface AnimatedProgressProps {
  value: number; // 0-1
  color?: string;
  height?: number;
  className?: string;
  showValue?: boolean;
}

export function AnimatedProgress({
  value,
  color = '#00FFFF',
  height = 4,
  className,
  showValue = false,
}: AnimatedProgressProps) {
  return (
    <div className={cn('relative', className)}>
      <div
        className="w-full rounded-full overflow-hidden bg-muted"
        style={{ height }}
      >
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
          initial={{ width: 0 }}
          animate={{ width: `${value * 100}%` }}
          transition={{ type: 'spring', stiffness: 200, damping: 25 }}
        />
      </div>
      {showValue && (
        <span className="absolute right-0 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
          <AnimatedPercentage value={value} decimals={0} />
        </span>
      )}
    </div>
  );
}

// Animated sentiment gauge (arc visualization)
interface AnimatedGaugeProps {
  value: number; // -1 to 1
  size?: number;
  strokeWidth?: number;
  className?: string;
}

export function AnimatedGauge({
  value,
  size = 120,
  strokeWidth = 8,
  className,
}: AnimatedGaugeProps) {
  const normalizedValue = (value + 1) / 2; // Convert -1..1 to 0..1
  const color = getSentimentColor(value);
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * Math.PI; // Half circle
  const offset = circumference * (1 - normalizedValue);

  return (
    <div className={cn('relative', className)} style={{ width: size, height: size / 2 + 20 }}>
      <svg width={size} height={size / 2 + 10} viewBox={`0 0 ${size} ${size / 2 + 10}`}>
        {/* Background arc */}
        <path
          d={`M ${strokeWidth / 2} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${size / 2}`}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-muted"
        />
        {/* Value arc */}
        <motion.path
          d={`M ${strokeWidth / 2} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${size / 2}`}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ type: 'spring', stiffness: 200, damping: 25 }}
        />
      </svg>
      {/* Value display */}
      <div className="absolute inset-x-0 bottom-0 text-center">
        <AnimatedSentimentScore score={value} size="md" />
      </div>
    </div>
  );
}
