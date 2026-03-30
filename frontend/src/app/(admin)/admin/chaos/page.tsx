import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ShieldCheck } from 'lucide-react';

export const metadata = {
  title: 'Chaos Dashboard',
};

export default function ChaosPage() {
  return (
    <Card className="max-w-lg mx-auto mt-8" data-testid="chaos-placeholder">
      <CardHeader className="text-center">
        <ShieldCheck className="w-10 h-10 mx-auto text-muted-foreground mb-2" />
        <CardTitle>Chaos Dashboard</CardTitle>
      </CardHeader>
      <CardContent className="text-center">
        <p className="text-muted-foreground">
          Chaos experiment management is coming soon.
        </p>
      </CardContent>
    </Card>
  );
}
