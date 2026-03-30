'use client';

import { Database, Upload, Zap } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { SCENARIOS, type ScenarioType } from '@/types/chaos';

const ICONS = {
  database: Database,
  upload: Upload,
  zap: Zap,
} as const;

interface ScenarioLibraryProps {
  selected: ScenarioType | null;
  onSelect: (scenario: ScenarioType) => void;
}

export function ScenarioLibrary({ selected, onSelect }: ScenarioLibraryProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {SCENARIOS.map((scenario) => {
        const Icon = ICONS[scenario.icon as keyof typeof ICONS] ?? Zap;
        const isSelected = selected === scenario.type;

        return (
          <Card
            key={scenario.type}
            data-testid={`scenario-card-${scenario.type}`}
            className={cn(
              'cursor-pointer transition-all hover:border-accent/50',
              isSelected && 'border-accent ring-1 ring-accent'
            )}
            onClick={() => onSelect(scenario.type)}
          >
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Icon className="w-5 h-5 text-muted-foreground" />
                <CardTitle className="text-sm">{scenario.title}</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">{scenario.description}</p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
