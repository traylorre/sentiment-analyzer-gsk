'use client';

import { motion } from 'framer-motion';
import { LayoutDashboard, Settings2, Bell, Cog } from 'lucide-react';
import { useViewStore, type ViewType } from '@/stores/view-store';
import { useHaptic } from '@/hooks/use-haptic';
import { cn } from '@/lib/utils';
import { UserMenu } from '@/components/auth/user-menu';

interface NavItem {
  view: ViewType;
  label: string;
  icon: typeof LayoutDashboard;
}

const NAV_ITEMS: NavItem[] = [
  { view: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { view: 'configs', label: 'Configurations', icon: Settings2 },
  { view: 'alerts', label: 'Alerts', icon: Bell },
  { view: 'settings', label: 'Settings', icon: Cog },
];

interface DesktopNavProps {
  className?: string;
}

export function DesktopNav({ className }: DesktopNavProps) {
  const { currentView, setView } = useViewStore();
  const haptic = useHaptic();

  const handleNavClick = (view: ViewType) => {
    if (view === currentView) return;
    haptic.light();
    setView(view);
  };

  return (
    <aside
      className={cn(
        'hidden md:flex flex-col',
        'w-64 h-screen',
        'bg-card border-r border-border',
        'fixed left-0 top-0',
        className
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
          <LayoutDashboard className="w-4 h-4 text-background" />
        </div>
        <span className="text-lg font-semibold text-foreground">Sentiment</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive = currentView === item.view;
          const Icon = item.icon;

          return (
            <button
              key={item.view}
              onClick={() => handleNavClick(item.view)}
              className={cn(
                'relative w-full flex items-center gap-3 px-3 py-2.5 rounded-lg',
                'text-left transition-colors duration-200',
                isActive
                  ? 'text-accent'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              )}
            >
              {/* Active background */}
              {isActive && (
                <motion.div
                  layoutId="desktop-nav-bg"
                  className="absolute inset-0 bg-accent/10 rounded-lg"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}

              {/* Active indicator */}
              {isActive && (
                <motion.div
                  layoutId="desktop-nav-indicator"
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r-full bg-accent"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}

              <Icon className="relative z-10 w-5 h-5" />
              <span className="relative z-10 font-medium">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* User section */}
      <div className="px-3 py-4 border-t border-border">
        <UserMenu className="w-full justify-start" />
      </div>
    </aside>
  );
}

// Desktop header for current view
interface DesktopHeaderProps {
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
  className?: string;
}

export function DesktopHeader({ title, subtitle, actions, className }: DesktopHeaderProps) {
  const { currentView } = useViewStore();

  const viewTitles: Record<ViewType, string> = {
    dashboard: 'Dashboard',
    configs: 'Configurations',
    alerts: 'Alerts',
    settings: 'Settings',
  };

  const displayTitle = title ?? viewTitles[currentView];

  return (
    <header
      className={cn(
        'hidden md:flex items-center justify-between',
        'h-16 px-6 border-b border-border bg-background',
        className
      )}
    >
      <div>
        <h1 className="text-xl font-semibold text-foreground">{displayTitle}</h1>
        {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </header>
  );
}
