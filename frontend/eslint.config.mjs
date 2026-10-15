import { defineConfig } from 'eslint/config';
import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';

// Flat config, required by eslint 9. Replaces .eslintrc.json, which was
// `extends: "next/core-web-vitals"` — the same rule set, imported directly.
// `next lint` was removed in Next 16, so the `lint` script now calls `eslint .`.
export default defineConfig([
  {
    extends: [...nextCoreWebVitals],
  },
  {
    // Playwright passes each fixture a callback named `use`, which this rule
    // mistakes for React's use() hook.
    files: ['tests/e2e/**'],
    rules: { 'react-hooks/rules-of-hooks': 'off' },
  },
]);
