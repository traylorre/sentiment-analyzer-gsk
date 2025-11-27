'use client';

import { motion } from 'framer-motion';
import { Settings2, Plus } from 'lucide-react';
import { PageTransition } from '@/components/layout/page-transition';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export default function ConfigsPage() {
  return (
    <PageTransition>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground md:hidden">Configurations</h1>
            <p className="text-muted-foreground mt-1">Manage your sentiment tracking configurations</p>
          </div>
          <Button className="gap-2">
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">New Config</span>
          </Button>
        </div>

        {/* Empty state */}
        <Card className="flex flex-col items-center justify-center py-16 text-center">
          <motion.div
            className="w-16 h-16 rounded-full bg-accent/10 flex items-center justify-center mb-4"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', delay: 0.1 }}
          >
            <Settings2 className="w-8 h-8 text-accent" />
          </motion.div>
          <motion.h3
            className="text-lg font-semibold text-foreground mb-2"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            No configurations yet
          </motion.h3>
          <motion.p
            className="text-muted-foreground max-w-sm mb-6"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            Create your first configuration to start tracking sentiment for your favorite tickers.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Button className="gap-2">
              <Plus className="w-4 h-4" />
              Create Configuration
            </Button>
          </motion.div>
        </Card>
      </div>
    </PageTransition>
  );
}
