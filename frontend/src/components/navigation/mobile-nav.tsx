'use client';

import { motion } from 'framer-motion';
import { LayoutDashboard, Settings2, Bell, Cog } from 'lucide-react';
import { useViewStore, type ViewType } from '@/stores/view-store';
import { useHaptic } from '@/hooks/use-haptic';
import { cn } from '@/lib/utils';

interface NavItem {
  view: ViewType;
  label: string;
  icon: typeof LayoutDashboard;
}

const NAV_ITEMS: NavItem[] = [
  { view: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { view: 'configs', label: 'Configs', icon: Settings2 },
  { view: 'alerts', label: 'Alerts', icon: Bell },
  { view: 'settings', label: 'Settings', icon: Cog },
];

interface MobileNavProps {
  className?: string;
}

export function MobileNav({ className }: MobileNavProps) {
  const { currentView, setView } = useViewStore();
  const haptic = useHaptic();

  const handleNavClick = (view: ViewType) => {
    if (view === currentView) return;
    haptic.light();
    setView(view);
  };

  return (
    <nav
      className={cn(
        'fixed bottom-0 left-0 right-0 z-30',
        'bg-card/80 backdrop-blur-xl border-t border-border',
        'pb-safe',
        'md:hidden', // Hide on desktop
        className
      )}
      role="tablist"
      aria-label="Main navigation"
    >
      <div className="flex items-center justify-around h-16">
        {NAV_ITEMS.map((item) => {
          const isActive = currentView === item.view;
          const Icon = item.icon;

          return (
            <button
              key={item.view}
              onClick={() => handleNavClick(item.view)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleNavClick(item.view);
                }
              }}
              className={cn(
                'relative flex flex-col items-center justify-center',
                'w-16 h-full',
                'transition-colors duration-200',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background'
              )}
              role="tab"
              aria-selected={isActive}
              aria-label={`${item.label} tab${isActive ? ', selected' : ''}`}
              tabIndex={0}
            >
              {/* Active indicator */}
              {isActive && (
                <motion.div
                  layoutId="mobile-nav-indicator"
                  className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-1 rounded-b-full bg-accent"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}

              {/* Icon */}
              <motion.div
                animate={{
                  scale: isActive ? 1.1 : 1,
                  y: isActive ? -2 : 0,
                }}
                transition={{ type: 'spring', stiffness: 400, damping: 20 }}
              >
                <Icon
                  className={cn(
                    'w-5 h-5 transition-colors duration-200',
                    isActive ? 'text-accent' : 'text-muted-foreground'
                  )}
                />
              </motion.div>

              {/* Label */}
              <motion.span
                className={cn(
                  'text-xs mt-1 transition-colors duration-200',
                  isActive ? 'text-accent font-medium' : 'text-muted-foreground'
                )}
                animate={{ opacity: isActive ? 1 : 0.7 }}
              >
                {item.label}
              </motion.span>

              {/* Glow effect when active */}
              {isActive && (
                <motion.div
                  className="absolute inset-0 bg-accent/5 rounded-lg"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
}

// Floating action button for mobile
interface FloatingActionButtonProps {
  onClick: () => void;
  icon: typeof LayoutDashboard;
  label: string;
  className?: string;
}

export function FloatingActionButton({
  onClick,
  icon: Icon,
  label,
  className,
}: FloatingActionButtonProps) {
  const haptic = useHaptic();

  const handleClick = () => {
    haptic.medium();
    onClick();
  };

  return (
    <motion.button
      onClick={handleClick}
      className={cn(
        'fixed right-4 bottom-20 z-20',
        'w-14 h-14 rounded-full',
        'bg-accent text-background',
        'shadow-lg shadow-accent/30',
        'flex items-center justify-center',
        'md:hidden', // Hide on desktop
        className
      )}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0, opacity: 0 }}
      aria-label={label}
    >
      <Icon className="w-6 h-6" />
    </motion.button>
  );
}
