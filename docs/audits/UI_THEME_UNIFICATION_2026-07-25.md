# Desktop UI Theme Unification — 2026-07-25

**Status:** Complete for `tokens.colors.text` / `tokens.colors.bg` (#4877, 2026-08-14).
`tokens.glass` and direct hex/RGB expressions remain open — see *Remaining migration debt*.

**Product decision:** Electron is the only official interface platform. Standalone browser/PWA
execution is deprecated and retained solely as an unsupported renderer-development preview.

## Outcome of this slice

The visible application frame now uses one semantic theme contract instead of independently
selecting design-token palette levels, MUI colors, and glass presets.

Completed surfaces:

- application canvas and ambient background;
- browser platform notice;
- top bar, search field, connection state, and view toggle;
- expanded and collapsed navigation sidebar;
- library view header and right-hand character pane;
- player frame, queue controls, and expanded queue;
- shared Paper, Card, Drawer, Dialog, input, tab, button, and tooltip defaults;
- settings and shared library dialogs;
- light/dark theme runtime variables, scrollbars, focus states, and reduced-motion behavior.

The migration also repaired the production TypeScript gate. `CacheHealthMonitor` now treats the
backend health timestamp as optional, matching the actual endpoint contract.

## Easy-fix follow-up

A bounded follow-up migrated 12 low-risk targets without changing their rendering structure,
state, playback behavior, or event contracts:

- shared typography, form-field, and skeleton styles;
- the application error boundary;
- search adornments and small settings surfaces;
- buffering, time, track, volume, and clear-queue controls.

The selected files went from 45 direct `tokens.colors.bg`, `tokens.colors.text`, or
`tokens.glass` references to zero. The semantic contract also gained explicit `onAccent` and
`onError` foreground roles so action text remains legible in both themes.

## Canonical contract

`auralis-web/frontend/src/theme/semanticTheme.ts` is the application-level theme boundary.

- Components use `themeVars` for semantic choices such as canvas, raised surface, primary text,
  muted text, default border, focus ring, status colors, and foregrounds placed on accent or
  destructive actions.
- `ThemeContext` resolves dark/light values and publishes one complete `--app-*` variable set.
- `themeConfig` maps MUI defaults to the same resolved palette.
- Design tokens remain canonical for spacing, typography, motion, radii, and fixed brand/audio
  colors.

New component-local palettes are not allowed. Glass is an overlay treatment, not a default
container material.

## Platform boundary

The React code is not removed because Electron loads that bundle as its renderer. Deprecation
means:

- no PWA/installability metadata is advertised;
- the manifest identifies browser execution as an unsupported preview;
- non-Electron execution shows a persistent platform notice;
- documentation no longer describes browsers or mobile devices as supported platforms;
- Vite remains available for development and visual inspection.

Native flows and release acceptance must be tested through Electron.

## Remaining migration debt

This is deliberately a substantial start, not a claim that every leaf component is finished.
Two string-level heuristics currently find:

- 206 production UI files containing direct hex/RGB color expressions outside theme token
  definitions and tests;
- ~~151 production UI files still selecting `tokens.colors.bg`, `tokens.colors.text`, or
  `tokens.glass` directly.~~ The `tokens.colors.text` / `tokens.colors.bg` half of this is
  **done** — #4877 migrated the last 65 files / 169 references on 2026-08-14, and
  `src/theme/__tests__/darkOnlyTokenLeak.test.ts` now fails the build on any new direct
  reference from production code, so it cannot regrow. `tokens.glass` is untouched and
  still open.

Those counts include legitimate fixed-output colors, SVG artwork, canvas visualizations, and
audio-semantic rendering, so they are an upper bound rather than 357 confirmed defects.
Follow-up review should prioritize interactive components and skip cases where runtime theming
is intentionally impossible, such as exported images.

## Follow-up order

1. Migrate the remaining shared primitives and inline-style player controls so light mode
   reaches every leaf.
2. Migrate library cards, tables, empty states, metadata forms, and playlist surfaces.
3. Migrate enhancement, discovery, cache-management, and diagnostic panels.
4. Classify remaining hardcoded colors as brand artwork, audio visualization, export-only, or
   genuine theme debt.
5. Add dark/light Electron screenshot regression coverage at supported desktop breakpoints.
6. Remove obsolete compatibility aliases after no production component consumes the old
   `--bg-*`, `--text-*`, or glass variable namespace.

## Validation for this slice

Required:

```bash
cd auralis-web/frontend
pnpm run type-check:prod
pnpm exec vitest run src/contexts/__tests__/ThemeContext.test.tsx \
  src/components/platform/__tests__/DesktopPlatformNotice.test.tsx \
  src/components/__tests__/ThemeToggle.test.tsx
pnpm run build
```

The expanded leaf-component baseline currently reports 151 passing tests and the same six
pre-existing failures before and after the easy-fix follow-up: five `TimeDisplay` formatting
and tooltip assertions, plus one `TrackDisplay` font-weight serialization assertion. No new
failure was introduced by the migration.

Release validation must additionally exercise the packaged Electron application; the browser
preview is not a release gate.
