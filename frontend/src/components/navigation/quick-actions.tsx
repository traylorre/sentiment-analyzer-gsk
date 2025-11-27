'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Plus,
  RefreshCw,
  Search,
  Share2,
  Download,
  Copy,
  Trash2,
  Edit2,
  MoreHorizontal,
  X,
} from 'lucide-react';
import { ActionSheet } from './bottom-sheet';
import { useHaptic } from '@/hooks/use-haptic';
import { cn } from '@/lib/utils';

interface QuickAction {
  id: string;
  label: string;
  icon: typeof Plus;
  onClick: () => void;
  variant?: 'default' | 'destructive';
}

interface QuickActionsProps {
  actions: QuickAction[];
  className?: string;
}

// Swipe-reveal quick actions (like iOS mail)
export function SwipeQuickActions({ actions, className }: QuickActionsProps) {
  return (
    <div className={cn('flex items-center gap-1', className)}>
      {actions.map((action) => {
        const Icon = action.icon;
        return (
          <button
            key={action.id}
            onClick={action.onClick}
            className={cn(
              'flex items-center justify-center w-14 h-full',
              'transition-colors',
              action.variant === 'destructive'
                ? 'bg-red-500 hover:bg-red-600 text-white'
                : 'bg-accent hover:bg-accent/90 text-background'
            )}
          >
            <Icon className="w-5 h-5" />
          </button>
        );
      })}
    </div>
  );
}

// Long-press context menu
interface ContextMenuProps {
  isOpen: boolean;
  onClose: () => void;
  position: { x: number; y: number };
  actions: QuickAction[];
}

export function ContextMenu({ isOpen, onClose, position, actions }: ContextMenuProps) {
  const haptic = useHaptic();

  const handleAction = (action: QuickAction) => {
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
            className="fixed inset-0 z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Menu */}
          <motion.div
            className="fixed z-50 min-w-48 bg-card border border-border rounded-xl shadow-xl overflow-hidden"
            style={{
              left: Math.min(position.x, window.innerWidth - 200),
              top: Math.min(position.y, window.innerHeight - 300),
            }}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ type: 'spring', duration: 0.2 }}
          >
            {actions.map((action, index) => {
              const Icon = action.icon;
              return (
                <button
                  key={action.id}
                  onClick={() => handleAction(action)}
                  className={cn(
                    'w-full px-4 py-3 flex items-center gap-3',
                    'text-left transition-colors',
                    'hover:bg-muted active:bg-muted',
                    index > 0 && 'border-t border-border',
                    action.variant === 'destructive'
                      ? 'text-red-500'
                      : 'text-foreground'
                  )}
                >
                  <Icon className="w-4 h-4" />
                  <span className="text-sm font-medium">{action.label}</span>
                </button>
              );
            })}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// Hook for long-press detection
export function useLongPress(
  callback: (position: { x: number; y: number }) => void,
  duration = 500
) {
  const [timer, setTimer] = useState<NodeJS.Timeout | null>(null);
  const haptic = useHaptic();

  const start = (e: React.TouchEvent | React.MouseEvent) => {
    const position =
      'touches' in e
        ? { x: e.touches[0].clientX, y: e.touches[0].clientY }
        : { x: e.clientX, y: e.clientY };

    const newTimer = setTimeout(() => {
      haptic.heavy();
      callback(position);
    }, duration);

    setTimer(newTimer);
  };

  const clear = () => {
    if (timer) {
      clearTimeout(timer);
      setTimer(null);
    }
  };

  return {
    onTouchStart: start,
    onTouchEnd: clear,
    onTouchMove: clear,
    onMouseDown: start,
    onMouseUp: clear,
    onMouseLeave: clear,
  };
}

// FAB with expandable actions
interface ExpandableFabProps {
  actions: QuickAction[];
  mainIcon?: typeof Plus;
  className?: string;
}

export function ExpandableFab({
  actions,
  mainIcon: MainIcon = Plus,
  className,
}: ExpandableFabProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const haptic = useHaptic();

  const handleToggle = () => {
    haptic.medium();
    setIsExpanded(!isExpanded);
  };

  const handleAction = (action: QuickAction) => {
    haptic.medium();
    action.onClick();
    setIsExpanded(false);
  };

  return (
    <>
      {/* Backdrop when expanded */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-30"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsExpanded(false)}
          />
        )}
      </AnimatePresence>

      <div className={cn('fixed right-4 bottom-20 z-40 md:hidden', className)}>
        {/* Action buttons */}
        <AnimatePresence>
          {isExpanded && (
            <div className="absolute bottom-16 right-0 space-y-3">
              {actions.map((action, index) => {
                const Icon = action.icon;
                return (
                  <motion.div
                    key={action.id}
                    className="flex items-center gap-3"
                    initial={{ opacity: 0, y: 20, scale: 0.8 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 20, scale: 0.8 }}
                    transition={{ delay: index * 0.05 }}
                  >
                    <span className="px-3 py-1.5 rounded-lg bg-card text-sm font-medium text-foreground shadow-lg">
                      {action.label}
                    </span>
                    <button
                      onClick={() => handleAction(action)}
                      className={cn(
                        'w-12 h-12 rounded-full flex items-center justify-center shadow-lg',
                        action.variant === 'destructive'
                          ? 'bg-red-500 text-white'
                          : 'bg-card text-foreground border border-border'
                      )}
                    >
                      <Icon className="w-5 h-5" />
                    </button>
                  </motion.div>
                );
              })}
            </div>
          )}
        </AnimatePresence>

        {/* Main FAB */}
        <motion.button
          onClick={handleToggle}
          className={cn(
            'w-14 h-14 rounded-full flex items-center justify-center',
            'bg-accent text-background shadow-lg shadow-accent/30',
            'transition-transform'
          )}
          animate={{ rotate: isExpanded ? 45 : 0 }}
          whileTap={{ scale: 0.95 }}
        >
          {isExpanded ? <X className="w-6 h-6" /> : <MainIcon className="w-6 h-6" />}
        </motion.button>
      </div>
    </>
  );
}

// More actions button with action sheet
interface MoreActionsButtonProps {
  actions: QuickAction[];
  title?: string;
  className?: string;
}

export function MoreActionsButton({ actions, title, className }: MoreActionsButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const haptic = useHaptic();

  return (
    <>
      <button
        onClick={() => {
          haptic.light();
          setIsOpen(true);
        }}
        className={cn(
          'p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors',
          className
        )}
        aria-label="More actions"
      >
        <MoreHorizontal className="w-5 h-5" />
      </button>

      <ActionSheet
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title={title}
        actions={actions.map((action) => ({
          label: action.label,
          icon: <action.icon className="w-5 h-5" />,
          onClick: action.onClick,
          variant: action.variant,
        }))}
      />
    </>
  );
}

// Common action presets
export const COMMON_ACTIONS = {
  refresh: (onClick: () => void): QuickAction => ({
    id: 'refresh',
    label: 'Refresh',
    icon: RefreshCw,
    onClick,
  }),
  search: (onClick: () => void): QuickAction => ({
    id: 'search',
    label: 'Search',
    icon: Search,
    onClick,
  }),
  share: (onClick: () => void): QuickAction => ({
    id: 'share',
    label: 'Share',
    icon: Share2,
    onClick,
  }),
  download: (onClick: () => void): QuickAction => ({
    id: 'download',
    label: 'Download',
    icon: Download,
    onClick,
  }),
  copy: (onClick: () => void): QuickAction => ({
    id: 'copy',
    label: 'Copy',
    icon: Copy,
    onClick,
  }),
  edit: (onClick: () => void): QuickAction => ({
    id: 'edit',
    label: 'Edit',
    icon: Edit2,
    onClick,
  }),
  delete: (onClick: () => void): QuickAction => ({
    id: 'delete',
    label: 'Delete',
    icon: Trash2,
    onClick,
    variant: 'destructive',
  }),
};
