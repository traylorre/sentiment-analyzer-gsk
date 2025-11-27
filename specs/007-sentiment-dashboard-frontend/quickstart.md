# Quickstart: Sentiment Dashboard Frontend

**Feature**: 007-sentiment-dashboard-frontend
**Date**: 2025-11-27

## Prerequisites

- Node.js 20 LTS
- npm 10+
- Git with GPG signing configured
- AWS Account (for Amplify deployment)
- Feature 006 backend deployed and accessible

## Initial Setup

### 1. Create the Frontend Directory

```bash
# From repository root
mkdir -p frontend
cd frontend
```

### 2. Initialize Next.js Project

```bash
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
```

Select these options:
- Would you like to use TypeScript? **Yes**
- Would you like to use ESLint? **Yes**
- Would you like to use Tailwind CSS? **Yes**
- Would you like to use `src/` directory? **Yes**
- Would you like to use App Router? **Yes**
- Would you like to customize the default import alias? **Yes** → `@/*`

### 3. Install Dependencies

```bash
# UI Components (shadcn/ui)
npx shadcn-ui@latest init

# Select: New York style, Zinc base color, CSS variables

# Add required shadcn components
npx shadcn-ui@latest add button card dialog input sheet skeleton slider switch toast tooltip

# Charts
npm install lightweight-charts

# Animation & Gestures
npm install framer-motion

# State Management
npm install zustand @tanstack/react-query

# Utilities
npm install clsx tailwind-merge

# Development
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom
npm install -D playwright @playwright/test
npm install -D @types/node
```

### 4. Configure Tailwind for Dark Fintech Theme

Update `tailwind.config.ts`:

```typescript
import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['class'],
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: 'rgb(var(--background) / <alpha-value>)',
        foreground: 'rgb(var(--foreground) / <alpha-value>)',
        primary: {
          DEFAULT: 'rgb(var(--primary) / <alpha-value>)',
          foreground: 'rgb(var(--primary-foreground) / <alpha-value>)',
        },
        card: {
          DEFAULT: 'rgb(var(--card) / <alpha-value>)',
          foreground: 'rgb(var(--card-foreground) / <alpha-value>)',
        },
        destructive: 'rgb(var(--destructive) / <alpha-value>)',
        success: 'rgb(var(--success) / <alpha-value>)',
        warning: 'rgb(var(--warning) / <alpha-value>)',
        muted: 'rgb(var(--muted) / <alpha-value>)',
        border: 'rgb(var(--border) / <alpha-value>)',
        ring: 'rgb(var(--ring) / <alpha-value>)',
        accent: 'rgb(var(--accent) / <alpha-value>)',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      keyframes: {
        'glow-pulse': {
          '0%, 100%': { boxShadow: '0 0 5px rgb(var(--accent))' },
          '50%': { boxShadow: '0 0 20px rgb(var(--accent))' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        'glow-pulse': 'glow-pulse 1s ease-in-out 2',
        'shimmer': 'shimmer 1.5s infinite',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};

export default config;
```

### 5. Configure Global Styles

Update `src/app/globals.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 10 10 10;
    --foreground: 245 245 245;
    --card: 15 15 15;
    --card-foreground: 245 245 245;
    --primary: 0 255 255;
    --primary-foreground: 10 10 10;
    --secondary: 30 30 30;
    --muted: 50 50 50;
    --accent: 0 255 255;
    --destructive: 239 68 68;
    --success: 34 197 94;
    --warning: 234 179 8;
    --border: 40 40 40;
    --ring: 0 255 255;
    --radius: 0.75rem;
  }
}

@layer base {
  body {
    @apply bg-background text-foreground;
    font-feature-settings: 'rlig' 1, 'calt' 1;
  }
}

/* Glassmorphism utility */
.glass {
  @apply bg-card/80 backdrop-blur-xl border border-accent/10;
}

/* Skeleton shimmer */
.skeleton {
  @apply bg-gradient-to-r from-muted/20 via-muted/40 to-muted/20 bg-[length:200%_100%] animate-shimmer;
}

/* Glow effect for updates */
.glow-update {
  @apply animate-glow-pulse;
}
```

### 6. Environment Variables

Create `.env.local`:

```bash
# API Configuration
NEXT_PUBLIC_API_URL=https://api.example.com

# AWS Cognito
NEXT_PUBLIC_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
NEXT_PUBLIC_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
NEXT_PUBLIC_COGNITO_DOMAIN=auth.example.com

# Feature Flags (optional)
NEXT_PUBLIC_ENABLE_HAPTICS=true
```

### 7. Configure Vitest

Create `vitest.config.ts`:

```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'tests/'],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
```

Create `tests/setup.ts`:

```typescript
import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock navigator.vibrate
Object.defineProperty(navigator, 'vibrate', {
  value: vi.fn(),
  writable: true,
});

// Mock matchMedia for prefers-reduced-motion
Object.defineProperty(window, 'matchMedia', {
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
```

### 8. Configure Playwright

Create `playwright.config.ts`:

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 13'] },
    },
    {
      name: 'Desktop Chrome',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
});
```

### 9. Configure AWS Amplify

Create `amplify.yml` in frontend directory:

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

### 10. Update package.json Scripts

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "typecheck": "tsc --noEmit"
  }
}
```

---

## Development Commands

```bash
# Start development server
npm run dev

# Run all unit tests
npm test

# Run tests in watch mode
npm run test:watch

# Run E2E tests
npm run test:e2e

# Run E2E tests with UI
npm run test:e2e:ui

# Type checking
npm run typecheck

# Lint
npm run lint

# Build for production
npm run build
```

---

## Project Structure Verification

After setup, verify the structure:

```bash
frontend/
├── src/
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   │   └── ui/           # shadcn components
│   ├── lib/
│   │   └── utils.ts      # cn() utility
│   └── types/
├── tests/
│   ├── setup.ts
│   ├── unit/
│   └── e2e/
├── public/
├── amplify.yml
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
├── vitest.config.ts
├── playwright.config.ts
└── package.json
```

---

## Deployment to AWS Amplify

### 1. Connect Repository

1. Go to AWS Amplify Console
2. Click "Host web app"
3. Connect GitHub repository
4. Select branch: `007-sentiment-dashboard-frontend` (or `main`)
5. Amplify auto-detects Next.js and uses `amplify.yml`

### 2. Configure Environment Variables

In Amplify Console → App settings → Environment variables:

```
NEXT_PUBLIC_API_URL=https://your-api.execute-api.us-east-1.amazonaws.com
NEXT_PUBLIC_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
NEXT_PUBLIC_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. Custom Domain (Optional)

1. Go to Domain management
2. Add your domain
3. Follow DNS configuration instructions

---

## Verification Checklist

- [ ] `npm run dev` starts server at localhost:3000
- [ ] Dark theme with cyan accents visible
- [ ] shadcn/ui components render correctly
- [ ] `npm test` runs without errors
- [ ] `npm run build` completes successfully
- [ ] Amplify deploys on git push

---

## Next Steps

1. Implement components per `data-model.md`
2. Build API client per `contracts/api-client.md`
3. Run `/speckit.tasks` to generate implementation tasks
