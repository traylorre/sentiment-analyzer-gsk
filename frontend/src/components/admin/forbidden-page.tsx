'use client';

import Link from 'next/link';
import { ShieldX } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

export function ForbiddenPage() {
  return (
    <div className="flex items-center justify-center min-h-[60vh] px-4">
      <Card className="w-full max-w-md text-center" data-testid="forbidden-page">
        <CardContent className="pt-8 pb-8 space-y-4">
          <ShieldX className="w-12 h-12 mx-auto text-muted-foreground" />
          <h1 className="text-2xl font-semibold text-foreground">
            Access Denied
          </h1>
          <p className="text-muted-foreground">
            You don&apos;t have permission to access this page.
          </p>
          <Button asChild variant="outline" data-testid="forbidden-back-button">
            <Link href="/">Back to Dashboard</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
