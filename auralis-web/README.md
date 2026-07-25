# Auralis Desktop Application Stack

> **Platform policy:** Auralis is a desktop application. The React renderer can be opened in a
> browser for development and visual review, but standalone browser/PWA use is deprecated and
> unsupported. Do not deploy this directory as an official web edition.

This directory contains the two local services embedded by the Electron application:

- `frontend/` — React and TypeScript desktop renderer.
- `backend/` — FastAPI service for the library, playback, enhancement, and WebSocket state.

Electron owns the supported product lifecycle and supplies native capabilities such as folder
selection and process management. The browser preview does not reproduce those guarantees.

## Architecture

```text
┌─────────────────────── Electron desktop application ───────────────────────┐
│                                                                            │
│  React renderer          HTTP / WebSocket           FastAPI backend        │
│  - TypeScript        <──────────────────────>       - Python 3.14+         │
│  - Material UI                                      - Auralis DSP          │
│  - Redux / Query                                    - SQLite library       │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

Both processes are local. Auralis does not require a hosted service or cloud library.

## Development prerequisites

- Python 3.14+
- Node.js 24+
- pnpm 10
- Rust stable, including the required `vendor/auralis-dsp` extension

See the root [README](../README.md) for the complete one-time environment setup and the current
recovery blockers.

## Component development

Until the canonical Electron launcher is repaired, run the backend and renderer separately.

Terminal 1:

```bash
source .venv/bin/activate
cd auralis-web/backend
python main.py --dev
```

Terminal 2:

```bash
cd auralis-web/frontend
pnpm install --frozen-lockfile
pnpm run dev
```

The Vite server listens on <http://localhost:3000>. That URL is an unsupported development
preview, not a production deployment target. A visible platform notice is intentional.

## Validation

```bash
cd auralis-web/frontend

pnpm run type-check:prod
pnpm run test:run
pnpm run build
```

Desktop packaging and smoke tests must run through `desktop/` and the cross-platform release
workflow. A successful Vite build proves only that the shared renderer bundles.

## Theme architecture

The renderer has one runtime semantic theme contract:

- `frontend/src/theme/semanticTheme.ts` defines application-level surfaces, text, borders,
  accents, status colors, focus treatment, and shadows for dark and light modes.
- `frontend/src/contexts/ThemeContext.tsx` publishes those values as `--app-*` properties.
- `frontend/src/theme/themeConfig.ts` maps MUI defaults to the same contract.
- Components should use `themeVars` for semantic decisions and design tokens for spacing,
  typography, motion, and fixed brand values.

Do not introduce a new component-local palette or make glass the default application surface.
Glass is reserved for overlays where translucency communicates elevation.

## Local API

The current local backend uses port `8765`.

- Health: `GET /api/health`
- API documentation in development: `GET /api/docs`
- Library endpoints: `/api/library/*`
- WebSocket transport: `/ws`

Endpoint details live in the FastAPI route definitions and generated OpenAPI document; this
README deliberately avoids duplicating a stale endpoint catalog.

## Platform support

| Runtime | Status | Purpose |
|---|---|---|
| Electron on Linux | Official target | AppImage, Flatpak, and `.deb` packaging |
| Electron on Windows x64 | Official target | NSIS installer |
| Electron on macOS Apple Silicon | Official target | ARM64 DMG |
| Standalone browser / PWA | Deprecated, unsupported | Renderer development and visual review only |
| Mobile browser | Unsupported | No official mobile platform |

## License

Auralis is licensed under AGPL-3.0. See the root [LICENSE](../LICENSE).
