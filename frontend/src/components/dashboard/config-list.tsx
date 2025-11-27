'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { Plus, FolderOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ConfigCard } from './config-card';
import type { Configuration } from '@/types/config';
import { cn } from '@/lib/utils';

interface ConfigListProps {
  configurations: Configuration[];
  activeConfigId: string | null;
  maxAllowed: number;
  isLoading?: boolean;
  onSelect: (configId: string) => void;
  onEdit: (config: Configuration) => void;
  onDelete: (configId: string) => void;
  onCreate: () => void;
  className?: string;
}

export function ConfigList({
  configurations,
  activeConfigId,
  maxAllowed,
  isLoading = false,
  onSelect,
  onEdit,
  onDelete,
  onCreate,
  className,
}: ConfigListProps) {
  const canCreate = configurations.length < maxAllowed;

  if (isLoading) {
    return (
      <div className={cn('space-y-4', className)}>
        {[...Array(3)].map((_, i) => (
          <ConfigCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (configurations.length === 0) {
    return (
      <EmptyState onCreateClick={onCreate} className={className} />
    );
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">
            Configurations
          </h2>
          <p className="text-sm text-muted-foreground">
            {configurations.length} of {maxAllowed} configurations
          </p>
        </div>

        <Button
          onClick={onCreate}
          disabled={!canCreate}
          size="sm"
          className="gap-2"
        >
          <Plus className="w-4 h-4" />
          New
        </Button>
      </div>

      {/* Config cards */}
      <motion.div layout className="space-y-3">
        <AnimatePresence mode="popLayout">
          {configurations.map((config) => (
            <ConfigCard
              key={config.configId}
              config={config}
              isActive={config.configId === activeConfigId}
              onSelect={() => onSelect(config.configId)}
              onEdit={() => onEdit(config)}
              onDelete={() => onDelete(config.configId)}
            />
          ))}
        </AnimatePresence>
      </motion.div>

      {/* Max limit warning */}
      {!canCreate && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-sm text-muted-foreground text-center py-2"
        >
          Maximum {maxAllowed} configurations reached
        </motion.p>
      )}
    </div>
  );
}

// Empty state component
interface EmptyStateProps {
  onCreateClick: () => void;
  className?: string;
}

function EmptyState({ onCreateClick, className }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'flex flex-col items-center justify-center py-12 text-center',
        className
      )}
    >
      <div className="w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mb-4">
        <FolderOpen className="w-8 h-8 text-muted-foreground" />
      </div>

      <h3 className="text-lg font-semibold text-foreground mb-1">
        No configurations yet
      </h3>

      <p className="text-sm text-muted-foreground mb-6 max-w-xs">
        Create your first configuration to start tracking sentiment for your
        favorite tickers.
      </p>

      <Button onClick={onCreateClick} className="gap-2">
        <Plus className="w-4 h-4" />
        Create Configuration
      </Button>
    </motion.div>
  );
}

// Skeleton loader
function ConfigCardSkeleton() {
  return (
    <div className="p-4 rounded-lg border border-border bg-card animate-pulse">
      <div className="flex items-start justify-between mb-3">
        <div className="space-y-2">
          <div className="h-5 w-32 bg-muted rounded" />
          <div className="h-3 w-20 bg-muted rounded" />
        </div>
        <div className="flex gap-1">
          <div className="h-8 w-8 bg-muted rounded" />
          <div className="h-8 w-8 bg-muted rounded" />
        </div>
      </div>

      <div className="flex gap-1.5 mb-3">
        <div className="h-6 w-12 bg-muted rounded-full" />
        <div className="h-6 w-14 bg-muted rounded-full" />
        <div className="h-6 w-10 bg-muted rounded-full" />
      </div>

      <div className="h-8 bg-muted rounded mb-3" />

      <div className="flex justify-between">
        <div className="h-3 w-12 bg-muted rounded" />
        <div className="h-3 w-24 bg-muted rounded" />
      </div>
    </div>
  );
}

// Grid layout variant
interface ConfigGridProps {
  configurations: Configuration[];
  activeConfigId: string | null;
  onSelect: (configId: string) => void;
  onEdit: (config: Configuration) => void;
  onDelete: (configId: string) => void;
  className?: string;
}

export function ConfigGrid({
  configurations,
  activeConfigId,
  onSelect,
  onEdit,
  onDelete,
  className,
}: ConfigGridProps) {
  return (
    <div
      className={cn(
        'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4',
        className
      )}
    >
      <AnimatePresence mode="popLayout">
        {configurations.map((config) => (
          <ConfigCard
            key={config.configId}
            config={config}
            isActive={config.configId === activeConfigId}
            onSelect={() => onSelect(config.configId)}
            onEdit={() => onEdit(config)}
            onDelete={() => onDelete(config.configId)}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}
