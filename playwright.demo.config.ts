import { defineConfig } from '@playwright/test';
import base from './playwright.config';

// Live-demo setup only (docs/demo/DEMO.md): creates a fresh demo company on the local stack.
// Run: npx playwright test -c playwright.demo.config.ts
export default defineConfig({
  ...base,
  testIgnore: [],
  testMatch: ['demo-setup.spec.ts'],
});
