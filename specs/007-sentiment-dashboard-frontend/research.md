# Research: Sentiment Dashboard Frontend

**Feature**: 007-sentiment-dashboard-frontend
**Date**: 2025-11-27
**Status**: Complete

## Research Tasks

### 1. TradingView Lightweight Charts for Robinhood-Style UI

**Decision**: Use TradingView Lightweight Charts v4.x

**Rationale**:
- Same library used by Robinhood for their charts
- 40kb bundle size (vs 400kb+ for Recharts/Chart.js)
- Financial-optimized: candlesticks, volume bars, crosshairs
- Native touch support with smooth panning/zooming
- Dark theme support built-in
- Sub-millisecond render times for 60fps animations

**Alternatives Considered**:
- **Recharts**: Too heavy (400kb), not financial-focused, basic animation support
- **Chart.js**: Heavy (200kb), good but not Robinhood aesthetic
- **Tremor**: Dashboard-focused but lacks interactive scrubbing for financial data
- **D3.js**: Maximum flexibility but requires custom implementation of everything

**Implementation Notes**:
```typescript
// Lightweight Charts setup for sentiment data
import { createChart, ColorType, LineStyle } from 'lightweight-charts';

const chart = createChart(container, {
  layout: {
    background: { type: ColorType.Solid, color: '#0a0a0a' },
    textColor: '#d1d5db',
  },
  grid: {
    vertLines: { color: 'rgba(0, 255, 255, 0.1)' },
    horzLines: { color: 'rgba(0, 255, 255, 0.1)' },
  },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: { color: '#00FFFF', style: LineStyle.Solid },
    horzLine: { color: '#00FFFF', style: LineStyle.Solid },
  },
});
```

---

### 2. Framer Motion for Gesture-Based Navigation

**Decision**: Use Framer Motion v11.x with gesture hooks

**Rationale**:
- Industry standard for React animations and gestures
- Physics-based spring animations (Robinhood-style bounce)
- Built-in gesture recognition: pan, drag, swipe, pinch
- Automatic GPU acceleration for 60fps
- `useReducedMotion` hook for accessibility
- `AnimatePresence` for smooth page transitions

**Alternatives Considered**:
- **React Spring**: Good physics but less gesture support
- **GSAP**: Powerful but overkill, larger bundle
- **CSS Animations**: No gesture support, limited physics
- **use-gesture + react-spring**: More setup, two libraries

**Key Patterns**:
```typescript
// Swipe navigation with spring physics
<motion.div
  drag="x"
  dragConstraints={{ left: 0, right: 0 }}
  dragElastic={0.2}
  onDragEnd={(_, info) => {
    if (Math.abs(info.offset.x) > threshold) {
      navigateToView(info.offset.x > 0 ? 'prev' : 'next');
    }
  }}
  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
/>
```

---

### 3. Haptic Feedback Implementation

**Decision**: Use Vibration API with graceful degradation

**Rationale**:
- Native browser API, no library needed
- Supported on modern mobile browsers (Chrome Android, Safari iOS 16.4+)
- Graceful degradation on unsupported devices (no error, no vibration)
- Three intensity levels: light (10ms), medium (20ms), heavy (30ms)

**Implementation**:
```typescript
// src/lib/utils/haptics.ts
export const haptic = {
  light: () => navigator.vibrate?.(10),
  medium: () => navigator.vibrate?.(20),
  heavy: () => navigator.vibrate?.(30),
  selection: () => navigator.vibrate?.([5, 10, 5]), // pattern
};

// Usage with hooks
export function useHaptic() {
  const prefersReducedMotion = useReducedMotion();
  return prefersReducedMotion ? { light: () => {}, medium: () => {}, heavy: () => {} } : haptic;
}
```

**Browser Support**:
- Chrome Android: Full support
- Safari iOS 16.4+: Partial (basic patterns)
- Desktop browsers: Not supported (graceful no-op)

---

### 4. shadcn/ui Component Customization for Dark Fintech Theme

**Decision**: Use shadcn/ui with custom dark theme configuration

**Rationale**:
- Copy-paste components (no npm dependency bloat)
- Built on Radix UI primitives (accessibility built-in)
- Tailwind-based (consistent with design system)
- Full control over styling for Robinhood aesthetic
- Sheet component perfect for bottom sheet gestures

**Theme Configuration**:
```css
/* globals.css - Dark fintech theme */
:root {
  --background: 10 10 10;        /* #0a0a0a near-black */
  --foreground: 245 245 245;     /* #f5f5f5 off-white */
  --card: 15 15 15;              /* #0f0f0f card background */
  --card-foreground: 245 245 245;
  --primary: 0 255 255;          /* #00FFFF cyan accent */
  --primary-foreground: 10 10 10;
  --secondary: 30 30 30;         /* #1e1e1e secondary bg */
  --muted: 50 50 50;
  --accent: 0 255 255;           /* Cyan for highlights */
  --destructive: 239 68 68;      /* #ef4444 red for negative */
  --success: 34 197 94;          /* #22c55e green for positive */
  --warning: 234 179 8;          /* #eab308 yellow for neutral */
  --border: 40 40 40;
  --ring: 0 255 255;             /* Cyan focus ring */
  --radius: 0.75rem;             /* Slightly rounded */
}
```

**Glassmorphism Effects**:
```css
.glass {
  background: rgba(15, 15, 15, 0.8);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(0, 255, 255, 0.1);
}
```

---

### 5. AWS Amplify Deployment for Next.js SSR

**Decision**: Use AWS Amplify Gen 2 with Next.js 14 support

**Rationale**:
- Native Next.js 14 App Router support (SSR, Server Actions)
- Automatic CI/CD from GitHub
- Built-in Cognito integration for auth
- Environment variables for API endpoints
- Edge caching for static assets
- Cheaper than Vercel at scale

**Configuration (amplify.yml)**:
```yaml
version: 1
applications:
  - frontend:
      phases:
        preBuild:
          commands:
            - npm ci
        build:
          commands:
            - npm run build
      artifacts:
        baseDirectory: .next
        files:
          - '**/*'
      cache:
        paths:
          - node_modules/**/*
          - .next/cache/**/*
      buildPath: frontend
    appRoot: frontend
```

**Environment Variables**:
- `NEXT_PUBLIC_API_URL`: Backend API base URL
- `NEXT_PUBLIC_COGNITO_USER_POOL_ID`: Cognito pool ID
- `NEXT_PUBLIC_COGNITO_CLIENT_ID`: Cognito app client ID

---

### 6. SSE (Server-Sent Events) for Real-Time Updates

**Decision**: Use native EventSource with React Query integration

**Rationale**:
- Native browser API (no library needed)
- One-way server-to-client (simpler than WebSocket)
- Automatic reconnection built-in
- Works with React Query for cache invalidation
- Backend already implements SSE endpoint

**Implementation Pattern**:
```typescript
// src/hooks/use-sse.ts
export function useSSE(configId: string) {
  const queryClient = useQueryClient();

  useEffect(() => {
    const eventSource = new EventSource(
      `${API_URL}/api/v2/configurations/${configId}/stream`
    );

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      queryClient.setQueryData(['sentiment', configId], data);
    };

    eventSource.onerror = () => {
      setConnectionStatus('reconnecting');
    };

    return () => eventSource.close();
  }, [configId]);
}
```

---

### 7. State Management Strategy

**Decision**: Zustand for client state + React Query for server state

**Rationale**:
- **Zustand**: Minimal boilerplate, 1kb, perfect for UI state (view, gestures, animations)
- **React Query**: Industry standard for async data, caching, background refresh
- Clear separation: Zustand for "what user is doing", React Query for "what server says"
- Both integrate well with React 18 Suspense

**State Split**:
```typescript
// Zustand - UI state
const useViewStore = create((set) => ({
  currentView: 'dashboard',
  isBottomSheetOpen: false,
  gestureProgress: 0,
}));

// React Query - Server state
const { data: sentiment } = useQuery({
  queryKey: ['sentiment', configId],
  queryFn: () => fetchSentiment(configId),
  staleTime: 5 * 60 * 1000, // 5 minutes
});
```

---

### 8. Performance Optimization Strategies

**Decision**: Multiple techniques for <200ms interactions and 90+ Lighthouse score

**Techniques**:

1. **Code Splitting**: Dynamic imports for chart components
```typescript
const SentimentChart = dynamic(() => import('@/components/charts/sentiment-chart'), {
  loading: () => <ChartSkeleton />,
  ssr: false, // Charts are client-side only
});
```

2. **Image Optimization**: Next.js Image component with blur placeholders

3. **Font Loading**: Inter font preloaded, system fallback
```html
<link rel="preload" href="/fonts/Inter.woff2" as="font" type="font/woff2" crossorigin />
```

4. **Animation Optimization**:
   - CSS transforms only (no layout thrashing)
   - `will-change` hints for animated elements
   - `requestAnimationFrame` for chart scrubbing

5. **Bundle Size**:
   - Target: <200kb initial JS
   - Tree-shaking for shadcn/ui (only import used components)
   - Lightweight Charts instead of heavier alternatives

---

### 9. Accessibility Compliance (WCAG 2.1 AA)

**Decision**: Built-in via Radix UI + custom enhancements

**Approach**:
- Radix UI primitives have ARIA attributes built-in
- Focus management for modals/sheets
- `prefers-reduced-motion` respected via Framer Motion hook
- Color contrast: cyan on dark meets 4.5:1 ratio
- Heat map includes text labels for color-blind users

**Key Implementations**:
```typescript
// Reduced motion support
const prefersReducedMotion = useReducedMotion();
const transition = prefersReducedMotion
  ? { duration: 0 }
  : { type: 'spring', stiffness: 300 };
```

---

## Summary of Technology Decisions

| Category | Choice | Bundle Impact |
|----------|--------|---------------|
| Framework | Next.js 14 (App Router) | ~85kb |
| UI Components | shadcn/ui (Tailwind + Radix) | ~15kb |
| Charts | TradingView Lightweight Charts | ~40kb |
| Animation | Framer Motion | ~25kb |
| State | Zustand + React Query | ~15kb |
| **Total Estimated** | | **~180kb** (gzipped) |

All NEEDS CLARIFICATION items resolved. Ready for Phase 1.
