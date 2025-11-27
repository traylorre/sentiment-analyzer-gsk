'use client';

import { useRef, useEffect, type ReactNode } from 'react';
import { motion, AnimatePresence, useMotionValue, useTransform, PanInfo } from 'framer-motion';
import { useViewStore, type ViewType } from '@/stores/view-store';
import { useHaptic } from '@/hooks/use-haptic';
import { cn } from '@/lib/utils';

interface SwipeViewProps {
  children: ReactNode;
  view: ViewType;
  className?: string;
}

const VIEW_ORDER: ViewType[] = ['dashboard', 'configs', 'alerts', 'settings'];

export function SwipeView({ children, view, className }: SwipeViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const {
    currentView,
    isGesturing,
    gestureProgress,
    gestureDirection,
    setView,
    startGesture,
    updateGesture,
    endGesture,
    cancelGesture,
  } = useViewStore();
  const haptic = useHaptic();

  const x = useMotionValue(0);
  const opacity = useTransform(x, [-200, 0, 200], [0.5, 1, 0.5]);

  const currentIndex = VIEW_ORDER.indexOf(currentView);
  const viewIndex = VIEW_ORDER.indexOf(view);
  const canSwipeLeft = currentIndex < VIEW_ORDER.length - 1;
  const canSwipeRight = currentIndex > 0;

  // Calculate gesture offset for visual feedback
  const gestureOffset = isGesturing
    ? gestureDirection === 'left'
      ? -gestureProgress * 100
      : gestureProgress * 100
    : 0;

  const handleDragStart = () => {
    haptic.light();
  };

  const handleDrag = (_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    const offset = info.offset.x;
    const absOffset = Math.abs(offset);

    // Determine direction and check if valid
    if (offset < 0 && !canSwipeLeft) {
      // Trying to swipe left but at the end - apply resistance
      x.set(offset * 0.2);
      return;
    }
    if (offset > 0 && !canSwipeRight) {
      // Trying to swipe right but at the start - apply resistance
      x.set(offset * 0.2);
      return;
    }

    x.set(offset);

    const direction = offset > 0 ? 'right' : 'left';
    const progress = Math.min(absOffset / 150, 1);

    startGesture(direction);
    updateGesture(progress);

    // Haptic at threshold
    if (absOffset >= 75 && absOffset < 80) {
      haptic.light();
    }
  };

  const handleDragEnd = (_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    const offset = info.offset.x;
    const velocity = info.velocity.x;
    const absOffset = Math.abs(offset);
    const absVelocity = Math.abs(velocity);

    // Determine if we should navigate
    const shouldNavigate = absOffset > 75 || absVelocity > 500;
    const direction = offset > 0 ? 'right' : 'left';

    if (shouldNavigate) {
      // Check if navigation is valid
      if (direction === 'left' && canSwipeLeft) {
        haptic.medium();
        setView(VIEW_ORDER[currentIndex + 1]);
      } else if (direction === 'right' && canSwipeRight) {
        haptic.medium();
        setView(VIEW_ORDER[currentIndex - 1]);
      }
    }

    // Animate back to center
    x.set(0);
    endGesture(false);
  };

  // Reset position when view changes
  useEffect(() => {
    x.set(0);
  }, [currentView, x]);

  // Only render if this is the current view
  if (view !== currentView) {
    return null;
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={view}
        ref={containerRef}
        className={cn('flex-1 overflow-hidden touch-pan-y', className)}
        style={{ x, opacity }}
        drag="x"
        dragConstraints={{ left: 0, right: 0 }}
        dragElastic={0.2}
        onDragStart={handleDragStart}
        onDrag={handleDrag}
        onDragEnd={handleDragEnd}
        initial={{
          opacity: 0,
          x: viewIndex > currentIndex ? 100 : -100
        }}
        animate={{
          opacity: 1,
          x: gestureOffset,
          transition: {
            type: 'spring',
            stiffness: 300,
            damping: 30
          }
        }}
        exit={{
          opacity: 0,
          x: viewIndex > currentIndex ? -100 : 100,
          transition: { duration: 0.2 }
        }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

// View indicator dots
interface ViewIndicatorProps {
  className?: string;
}

export function ViewIndicator({ className }: ViewIndicatorProps) {
  const { currentView, setView } = useViewStore();
  const haptic = useHaptic();

  return (
    <div className={cn('flex items-center justify-center gap-2', className)}>
      {VIEW_ORDER.map((view) => (
        <button
          key={view}
          onClick={() => {
            haptic.light();
            setView(view);
          }}
          className={cn(
            'w-2 h-2 rounded-full transition-all duration-300',
            currentView === view
              ? 'bg-accent w-6'
              : 'bg-muted-foreground/30 hover:bg-muted-foreground/50'
          )}
          aria-label={`Go to ${view} view`}
        />
      ))}
    </div>
  );
}

// Container that holds all swipe views
interface SwipeContainerProps {
  children: ReactNode;
  className?: string;
}

export function SwipeContainer({ children, className }: SwipeContainerProps) {
  return (
    <div className={cn('flex-1 flex flex-col overflow-hidden', className)}>
      {children}
    </div>
  );
}
