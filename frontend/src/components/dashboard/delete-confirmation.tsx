'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Trash2, X, Undo2, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface DeleteConfirmationProps {
  isOpen: boolean;
  itemName: string;
  onConfirm: () => void;
  onCancel: () => void;
  isDeleting?: boolean;
}

export function DeleteConfirmation({
  isOpen,
  itemName,
  onConfirm,
  onCancel,
  isDeleting = false,
}: DeleteConfirmationProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onCancel}
          />

          {/* Dialog */}
          <motion.div
            className="fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 p-4"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2 }}
          >
            <div className="rounded-lg border border-border bg-background shadow-lg overflow-hidden">
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b border-border">
                <h2 className="text-lg font-semibold text-foreground">
                  Delete Configuration
                </h2>
                <button
                  onClick={onCancel}
                  className="p-1 rounded-md hover:bg-muted transition-colors"
                  disabled={isDeleting}
                >
                  <X className="w-5 h-5 text-muted-foreground" />
                </button>
              </div>

              {/* Content */}
              <div className="p-4 space-y-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center flex-shrink-0">
                    <AlertTriangle className="w-6 h-6 text-red-500" />
                  </div>
                  <div>
                    <p className="text-foreground">
                      Are you sure you want to delete{' '}
                      <span className="font-semibold">{itemName}</span>?
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      This action cannot be undone. All associated alerts will
                      also be deleted.
                    </p>
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="flex gap-3 p-4 border-t border-border">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={onCancel}
                  disabled={isDeleting}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  className="flex-1 gap-2"
                  onClick={onConfirm}
                  disabled={isDeleting}
                >
                  {isDeleting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                      Deleting...
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-4 h-4" />
                      Delete
                    </>
                  )}
                </Button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// Toast-style undo notification
interface UndoToastProps {
  message: string;
  isVisible: boolean;
  onUndo: () => void;
  onDismiss: () => void;
  duration?: number;
}

export function UndoToast({
  message,
  isVisible,
  onUndo,
  onDismiss,
  duration = 5000,
}: UndoToastProps) {
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    if (!isVisible) {
      setProgress(100);
      return;
    }

    const startTime = Date.now();
    const endTime = startTime + duration;

    const interval = setInterval(() => {
      const now = Date.now();
      const remaining = Math.max(0, endTime - now);
      const progressValue = (remaining / duration) * 100;
      setProgress(progressValue);

      if (remaining <= 0) {
        clearInterval(interval);
        onDismiss();
      }
    }, 50);

    return () => clearInterval(interval);
  }, [isVisible, duration, onDismiss]);

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          className="fixed bottom-4 right-4 z-50 max-w-sm"
          initial={{ opacity: 0, y: 20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.2 }}
        >
          <div className="rounded-lg border border-border bg-background shadow-lg overflow-hidden">
            {/* Progress bar */}
            <div className="h-1 bg-muted">
              <motion.div
                className="h-full bg-accent"
                initial={{ width: '100%' }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.05 }}
              />
            </div>

            <div className="flex items-center gap-3 p-3">
              <p className="flex-1 text-sm text-foreground">{message}</p>
              <Button
                variant="ghost"
                size="sm"
                onClick={onUndo}
                className="gap-1.5 text-accent hover:text-accent"
              >
                <Undo2 className="w-4 h-4" />
                Undo
              </Button>
              <button
                onClick={onDismiss}
                className="p-1 rounded-md hover:bg-muted transition-colors"
              >
                <X className="w-4 h-4 text-muted-foreground" />
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// Inline delete button with confirmation
interface InlineDeleteProps {
  onDelete: () => void;
  itemName: string;
  className?: string;
}

export function InlineDelete({ onDelete, itemName, className }: InlineDeleteProps) {
  const [showConfirm, setShowConfirm] = useState(false);

  const handleDelete = useCallback(() => {
    onDelete();
    setShowConfirm(false);
  }, [onDelete]);

  if (showConfirm) {
    return (
      <div className={cn('flex items-center gap-2', className)}>
        <span className="text-sm text-muted-foreground">Delete?</span>
        <Button
          variant="destructive"
          size="sm"
          onClick={handleDelete}
        >
          Yes
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowConfirm(false)}
        >
          No
        </Button>
      </div>
    );
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      className={cn('text-red-500 hover:text-red-600 hover:bg-red-500/10', className)}
      onClick={() => setShowConfirm(true)}
    >
      <Trash2 className="w-4 h-4" />
    </Button>
  );
}
