'use client';

import { useEffect, useRef, type ReactNode } from 'react';
import { motion, AnimatePresence, PanInfo, useMotionValue, useTransform } from 'framer-motion';
import { X } from 'lucide-react';
import { useViewStore } from '@/stores/view-store';
import { useHaptic } from '@/hooks/use-haptic';
import { cn } from '@/lib/utils';

interface BottomSheetProps {
  children: ReactNode;
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  className?: string;
  snapPoints?: number[]; // Heights in vh (e.g., [25, 50, 90])
  initialSnap?: number; // Index into snapPoints
}

export function BottomSheet({
  children,
  isOpen,
  onClose,
  title,
  className,
  snapPoints = [50, 90],
  initialSnap = 0,
}: BottomSheetProps) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const haptic = useHaptic();

  const y = useMotionValue(0);
  const backdropOpacity = useTransform(y, [-500, 0], [0.8, 0]);

  // Calculate height based on snap points
  const initialHeight = snapPoints[initialSnap];
  const maxHeight = Math.max(...snapPoints);
  const minHeight = Math.min(...snapPoints);

  // Close on escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Lock body scroll when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const handleDrag = (_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    // Only handle vertical drag
    if (Math.abs(info.offset.y) > Math.abs(info.offset.x)) {
      y.set(info.offset.y);
    }
  };

  const handleDragEnd = (_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    const offset = info.offset.y;
    const velocity = info.velocity.y;

    // If dragged down more than 100px or fast downward velocity, close
    if (offset > 100 || velocity > 500) {
      haptic.light();
      onClose();
    } else {
      // Snap back
      y.set(0);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            style={{ opacity: backdropOpacity }}
          />

          {/* Sheet */}
          <motion.div
            ref={sheetRef}
            className={cn(
              'fixed bottom-0 left-0 right-0 z-50',
              'bg-card rounded-t-2xl shadow-2xl',
              'border-t border-border',
              className
            )}
            style={{
              y,
              height: `${initialHeight}vh`,
              maxHeight: `${maxHeight}vh`,
            }}
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{
              type: 'spring',
              damping: 30,
              stiffness: 300,
            }}
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0.1, bottom: 0.5 }}
            onDrag={handleDrag}
            onDragEnd={handleDragEnd}
          >
            {/* Drag handle */}
            <div className="flex justify-center pt-3 pb-2">
              <div className="w-10 h-1 rounded-full bg-muted-foreground/30" />
            </div>

            {/* Header */}
            {title && (
              <div className="flex items-center justify-between px-4 pb-4 border-b border-border">
                <h2 className="text-lg font-semibold text-foreground">{title}</h2>
                <button
                  onClick={onClose}
                  className="p-2 rounded-full hover:bg-muted transition-colors"
                  aria-label="Close"
                >
                  <X className="w-5 h-5 text-muted-foreground" />
                </button>
              </div>
            )}

            {/* Content */}
            <div className="overflow-auto h-full px-4 py-4">
              {children}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// Action sheet variant for quick actions
interface ActionSheetProps {
  isOpen: boolean;
  onClose: () => void;
  actions: ActionSheetAction[];
  title?: string;
  cancelLabel?: string;
}

interface ActionSheetAction {
  label: string;
  icon?: ReactNode;
  onClick: () => void;
  variant?: 'default' | 'destructive';
}

export function ActionSheet({
  isOpen,
  onClose,
  actions,
  title,
  cancelLabel = 'Cancel',
}: ActionSheetProps) {
  const haptic = useHaptic();

  const handleAction = (action: ActionSheetAction) => {
    haptic.medium();
    action.onClick();
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Sheet */}
          <motion.div
            className="fixed bottom-0 left-0 right-0 z-50 p-4 pb-safe"
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{
              type: 'spring',
              damping: 30,
              stiffness: 300,
            }}
          >
            {/* Actions */}
            <div className="bg-card rounded-xl overflow-hidden mb-2">
              {title && (
                <div className="px-4 py-3 text-center border-b border-border">
                  <span className="text-sm text-muted-foreground">{title}</span>
                </div>
              )}
              {actions.map((action, index) => (
                <button
                  key={index}
                  onClick={() => handleAction(action)}
                  className={cn(
                    'w-full px-4 py-3 flex items-center justify-center gap-3',
                    'text-base font-medium transition-colors',
                    'hover:bg-muted active:bg-muted',
                    index > 0 && 'border-t border-border',
                    action.variant === 'destructive'
                      ? 'text-red-500'
                      : 'text-foreground'
                  )}
                >
                  {action.icon}
                  {action.label}
                </button>
              ))}
            </div>

            {/* Cancel button */}
            <button
              onClick={onClose}
              className={cn(
                'w-full px-4 py-3 rounded-xl',
                'bg-card text-accent font-semibold',
                'hover:bg-muted active:bg-muted transition-colors'
              )}
            >
              {cancelLabel}
            </button>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// Hook to use bottom sheet from view store
export function useBottomSheet() {
  const { isBottomSheetOpen, bottomSheetContent, openBottomSheet, closeBottomSheet } =
    useViewStore();

  return {
    isOpen: isBottomSheetOpen,
    content: bottomSheetContent,
    open: openBottomSheet,
    close: closeBottomSheet,
  };
}
