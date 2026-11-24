# Auralis Desktop Application Stack

> **Platform policy:** Auralis is a desktop application. The React renderer can be opened in a
> browser for development and visual review, but standalone browser or PWA use is unsupported;
> the renderer shows a platform notice (`frontend/src/components/platform/DesktopPlatformNotice.tsx`)
> to make that visible. Do not deploy this directory as a web edition.

This directory holds the two local services the Electron app (`../desktop/`) embeds:

| Package | What it is | Docs |
|---|---|---|
| `backend/` | FastAPI service on `127.0.0.1:8765`: library, playback, enhancement, batch processing, and one WebSocket for state and audio streaming | [backend-api.md](../docs/subsystems/backend-api.md), [WEBSOCKET_API.md](backend/WEBSOCKET_API.md), [CONFIG.md](backend/CONFIG.md) |
| `frontend/` | React 18, TypeScript, Vite, MUI, Redux Toolkit, TanStack Query renderer | [frontend.md](../docs/subsystems/frontend.md) |

```text
Electron  ->  React renderer  <-- HTTP / WebSocket (:8765) -->  FastAPI backend
                                                                 -> HybridProcessor DSP, SQLite library
```

Both processes are local; Auralis needs no hosted service. Electron owns the product lifecycle
(starting and stopping the backend, native folder dialogs). Architecture and data flow:
[docs/architecture/overview.md](../docs/architecture/overview.md) and
[data-flow.md](../docs/architecture/data-flow.md). Defenses:
[SECURITY_MODEL.md](../docs/security/SECURITY_MODEL.md).

## Development

One-time environment setup (Python 3.14, Node 24, pnpm 10, the Rust `vendor/auralis-dsp`
extension) is in the root [README](../README.md) and the setup guides
[backend](../docs/development/DEVELOPMENT_SETUP_BACKEND.md) and
[frontend](../docs/development/DEVELOPMENT_SETUP_FRONTEND.md).

From the repository root, `pnpm run dev` starts Electron with the backend on :8765 and Vite on
:3000. `python launch-auralis-web.py --dev --no-browser` starts the same two servers for a
browser preview. To run the packages separately:

```bash
# terminal 1: backend (the --dev flag enables Swagger at /api/docs and the Vite origins)
source .venv/bin/activate && cd auralis-web/backend && python main.py --dev

# terminal 2: renderer
cd auralis-web/frontend && pnpm install --frozen-lockfile && pnpm run dev
```

Validation (frontend):

```bash
pnpm run type-check:prod
pnpm run test:memory      # 2 GB heap; plain test runs can run out of memory
pnpm run build
```

A successful Vite build proves only that the renderer bundles; packaging and smoke tests go
through `desktop/` and the release workflow. Backend tests: see
[TESTING_GUIDELINES.md](../docs/development/TESTING_GUIDELINES.md) (they open the real library
under `~/.auralis`, so isolate `HOME`).

## Theme

The renderer has one semantic theme contract: `frontend/src/theme/semanticTheme.ts` defines
surfaces, text, borders, accents, status colors, focus and shadows for dark and light modes;
`frontend/src/contexts/ThemeContext.tsx` publishes them as `--app-*` properties;
`frontend/src/theme/themeConfig.ts` maps MUI defaults onto the same contract. Components use
`themeVars` for semantic decisions and design tokens (`@/design-system`) for spacing, typography,
motion and fixed brand values. Do not add component-local palettes; glass is for overlays only.

## Local API

Health is `GET /api/health`, readiness `GET /api/ready`, the WebSocket is `/ws`. The route catalog
is in [backend-api.md](../docs/subsystems/backend-api.md); in dev mode the generated OpenAPI
documentation is at `/api/docs`.

## Platform support

| Runtime | Status | Package |
|---|---|---|
| Electron on Linux x64 | Official | AppImage, `.deb`, Flatpak |
| Electron on Windows x64 | Official | NSIS installer |
| Electron on macOS Apple Silicon | Official | arm64 DMG |
| Standalone browser / PWA | Unsupported | Development and visual review only |
| Mobile browser | Unsupported | None |

## License

AGPL-3.0, see the root [LICENSE](../LICENSE).
