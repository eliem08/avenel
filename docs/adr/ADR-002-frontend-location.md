# ADR-002: Frontend location — the Vite console lives at the repository root

**Status:** Accepted (Phase 5c-1, pending human review)
**Date:** 3 November 2026
**Supersedes:** the `/apps/web` row of ARCHITECTURE.md C.3

## Context

ADR-001 chose a Vite + React 18 SPA. The code ended up in two places: a Next.js draft in `/apps/web` (abandoned, never built or deployed) and the Vite app at the repository root (`/src`, `index.html`, `vite.config.ts`), which was mixed with code from an unrelated product. C.3 still described `/apps/web` as a Next.js console.

## Decision

- The AVENEL console is the Vite SPA at the repository root: `index.html`, `vite.config.ts`, `/src`, `/public`, `/e2e`.
- `/apps/web` is deleted. `/apps` contains only `/apps/api`.
- The build (`npm run build` → `dist/`) is served by Nginx (`docker/Dockerfile.web`, `docker/nginx.conf`).
- The browser talks to the API only through a TypeScript client generated from `contracts/openapi.yaml` (`src/api/schema.d.ts`), and authenticates with OIDC Authorization Code + PKCE against Keycloak (`oidc-client-ts`, tokens held in memory).
- Tailwind `theme.colors` is replaced (not extended) by the Part E tokens. `transparent` and `currentColor` are the only non-Part-E values, because they are not colors (they let borders and icons inherit). Fonts are self-hosted in `/public/fonts` and declared with `@font-face` in `src/styles/fonts.css`.

## Consequences

- Moving the console under `/apps/web` later is a file move only; nothing depends on the root location except build config.
- The repository root holds both Python (backend) and Node (console) tooling. The Makefile is the single entry point for both.
