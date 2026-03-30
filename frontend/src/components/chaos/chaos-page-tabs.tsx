'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { ExperimentsTab } from './experiments-tab';
import { ReportsTab } from './reports-tab';
import { MetricsPanel } from './metrics-panel';

type Tab = 'experiments' | 'reports';

export function ChaosPageTabs() {
  const [activeTab, setActiveTab] = useState<Tab>('experiments');

  return (
    <div className="space-y-6" data-testid="chaos-tabs">
      {/* Tab bar */}
      <div className="flex gap-1 border-b border-border">
        {(['experiments', 'reports'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            data-testid={`chaos-tab-${tab}`}
            className={cn(
              'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
              activeTab === tab
                ? 'border-accent text-accent'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
          >
            {tab === 'experiments' ? 'Experiments' : 'Reports'}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'experiments' && (
        <>
          <ExperimentsTab />
          <MetricsPanel />
        </>
      )}
      {activeTab === 'reports' && <ReportsTab />}
    </div>
  );
}
