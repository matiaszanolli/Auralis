# Frontend Development

Per-side depth for working on the React renderer in `auralis-web/frontend/` (React 18, TypeScript,
Redux Toolkit, MUI, Vite 8, Vitest 4): running it, configuration, debugging, tooling and common
failures. Installing and launching the project is in [FIRST_TIME_SETUP.md](../../FIRST_TIME_SETUP.md);
ground rules, CI gates and the PR flow are in [CONTRIBUTING.md](../CONTRIBUTING.md). The renderer's
structure (state, hooks, REST and WebSocket layers, design system, components) is in
[subsystems/frontend.md](../subsystems/frontend.md).

The renderer ships inside Electron. The Vite page in a browser is a developer preview, not a
supported web edition.

---

## Running the renderer

The normal paths start the backend for you:

```bash
pnpm run dev                                       # repository root: backend + Vite + Electron
python launch-auralis-web.py --dev --no-browser    # backend + Vite, no Electron
```

To run Vite alone against a backend you started yourself (see
[DEVELOPMENT_SETUP_BACKEND.md](DEVELOPMENT_SETUP_BACKEND.md#running-the-backend-alone)):

```bash
cd auralis-web/frontend
pnpm run dev            # Vite on http://localhost:3000 with hot module replacement
```

Vite proxies `/api` and `/ws` to `127.0.0.1:${AURALIS_PORT:-8765}`. The dev WebSocket connects to
the backend port directly (`auralis-web/frontend/src/config/api.ts`), so the backend must run in
dev mode: its origin allowlist accepts Vite only on ports 3000 to 3006 and only with `--dev`.

A production bundle is built into `dist/` (not `build/`) and is what the backend serves when it
is launched without `--dev`:

```bash
pnpm run build          # vite build -> auralis-web/frontend/dist/
pnpm run preview        # serve dist/ locally
```

---

## Configuration

Nothing needs configuring for development, and no `.env` file is required.

| Variable | Read by | Effect |
|----------|---------|--------|
| `AURALIS_PORT` | `auralis-web/frontend/vite.config.mts` | Backend port for the proxy and the dev WebSocket (default 8765). The launcher sets it from `--port` |
| `VITE_API_URL` | `auralis-web/frontend/src/config/api.ts` | Absolute API base URL. An absolute value also moves the WebSocket |
| `VITE_WS_URL` | `auralis-web/frontend/src/config/api.ts` | WebSocket base URL; wins over `VITE_API_URL` |

Production pages talk to their own origin. `VITE_BACKEND_PORT` is derived from `AURALIS_PORT` at
build time and is not meant to be set. Local overrides go in `auralis-web/frontend/.env.local`,
which git ignores. Backend variables are listed in
[auralis-web/backend/CONFIG.md](../../auralis-web/backend/CONFIG.md).

---

## Scripts

All are in `auralis-web/frontend/package.json` and run from that directory.

| Script | Purpose |
|--------|---------|
| `pnpm run dev` | Vite dev server |
| `pnpm run build` | Production bundle into `dist/` |
| `pnpm run type-check` | `tsc --noEmit` over every source and test file |
| `pnpm run type-check:prod` | `tsc --noEmit -p tsconfig.build.json`, production code only; the CI gate |
| `pnpm run test:memory` | One full Vitest pass with a 2 GB heap; the plain run can run out of memory |
| `pnpm test` | Vitest in watch mode |
| `pnpm run test:run` | One pass with the default heap, for a file or directory |
| `pnpm run test:ui` | Vitest UI |
| `pnpm run test:coverage` | V8 coverage report |
| `pnpm run test:ci`, `test:baseline`, `test:baseline:update` | The CI ratchet; see below |
| `pnpm run test:weak`, `test:weak:update` | The weak-spec gate and its baseline |

Scope the inner loop to what you changed:

```bash
pnpm run test:memory -- src/components/player          # a directory
pnpm test Sidebar.test.tsx                             # watch mode, filtered by path substring
pnpm test -t "queue"                                   # filtered by test name
```

[frontend/testing/TESTING_COMMANDS.md](../frontend/testing/TESTING_COMMANDS.md) is the full command
sheet.

---

## Debugging

- **Electron.** Dev mode opens DevTools with the window (`desktop/main.js`).
- **Browser.** The Network tab shows REST calls (relative URLs through the proxy) and the single
  WebSocket; the Console shows renderer errors. Production bundles strip `console.*`, so debug with
  a dev server.
- **Redux.** The store enables Redux DevTools in dev (`auralis-web/frontend/src/store/index.ts`).
  Redux is the source of truth for playback and the queue; do not add state that shadows it from the WebSocket.
- **Backend side.** For a failing request or stream, read the backend's DEBUG log and call the
  endpoint from `/api/docs` ([DEVELOPMENT_SETUP_BACKEND.md](DEVELOPMENT_SETUP_BACKEND.md#debugging)).
  Frontend WebSocket and REST types must match the backend `schemas/` package.
- **Mocks.** Tests use MSW. Handlers and fixtures live in `auralis-web/frontend/src/test/mocks/`
  (`handlers.ts`, `mockData.ts`, `server.ts`). A request to `/api/` with no handler fails the test.

---

## Tooling

TypeScript is the only static check: the project configures no ESLint or Prettier. `auralis-web/frontend/tsconfig.json`
is strict with `noUnusedLocals` and `noUnusedParameters`, and `@/*` maps to `src/*`. The same alias
is declared in `auralis-web/frontend/vite.config.mts` and `auralis-web/frontend/vitest.config.ts`.

CI gates the frontend runs (`.github/workflows/frontend-test.yml`, `frontend-typecheck.yml`):

- `pnpm run type-check:prod` must be clean.
- `pnpm run test:ci` followed by `pnpm run test:baseline` ratchets Vitest failures against
  `auralis-web/frontend/test-baseline.json`, which is empty, so any failing test is new.
- `pnpm run test:weak` rejects new weak specs against `auralis-web/frontend/weak-tests-baseline.json`.

When a change fixes a failing test, regenerate the baseline with
`pnpm run test:ci && pnpm run test:baseline:update`. The update refuses to run when the installed
`jsdom` or `vitest` differs from `pnpm-lock.yaml`, so run `pnpm install --frozen-lockfile` first.

After deleting components or styles, also run `pnpm run test:memory -- src/design-system`: the
`unreadTokens` test fails when a design token is no longer read anywhere.

Test conventions:

- Use `render` from `@/test/test-utils`. It wraps Redux (a fresh store per test), TanStack Query,
  the theme and the toast and playback-session providers, with no router.
- `auralis-web/frontend/src/test/setup.ts` replaces `WebSocketContext` with a fake connected
  context for every test; a test of the real context calls `vi.unmock('../contexts/WebSocketContext')`.
- Tests use `vi.*`, never `jest.*`. Colocate `*.test.ts(x)` beside the source or in a `__tests__/`
  folder.
- A `useVirtualizer` option such as `getItemKey` must be a `useCallback`-stable function. An inline
  closure re-renders from inside render and loops.

More: [subsystems/frontend.md](../subsystems/frontend.md#9-testing), `auralis-web/frontend/src/test/README.md` and
[TESTING_GUIDELINES.md](TESTING_GUIDELINES.md).

---

## IDE

- **VS Code.** Use the workspace TypeScript version so the `@/` alias resolves from
  `auralis-web/frontend/tsconfig.json`.
- **WebStorm / JetBrains.** Open the repository root, mark `auralis-web/frontend/src` as a Sources
  Root, use Node 24 and pnpm, and add a Vitest run configuration with working directory
  `auralis-web/frontend`.

---

## Common failures

| Symptom | Cause and fix |
|---------|---------------|
| `pnpm: command not found` | Install Node 24+, then `corepack enable` |
| `Install Node.js and run pnpm --dir auralis-web/frontend install first` | The launcher cannot find `node_modules/vite`. Run `pnpm --dir auralis-web/frontend install --frozen-lockfile` |
| Port 3000 in use | The launcher passes `--strictPort` and exits. Stop the other process. A bare `pnpm run dev` moves to the next free port, which the backend accepts only up to 3006 |
| WebSocket connection fails or the page cannot reach the backend | The backend is not running, runs on another port than `AURALIS_PORT`, or is not in dev mode. Check `curl http://127.0.0.1:8765/api/health` |
| `/api` requests return 404 or 502 in Vite | The proxy target is down or on a different port. Set `AURALIS_PORT` when starting Vite |
| `launch-auralis-web.py` says `Built frontend missing` | Run `pnpm run build`, or launch with `--dev` |
| `Cannot find module '@/...'` in the editor | The editor is not using the workspace `auralis-web/frontend/tsconfig.json`. Restart the TypeScript server |
| Vitest runs out of memory | Run `pnpm run test:memory`, or scope the run to a directory |
| `test:baseline:update` refuses to run | Installed `jsdom` or `vitest` differs from the lockfile. Run `pnpm install --frozen-lockfile` |
| Dependency state looks wrong | Delete `node_modules` and run `pnpm install --frozen-lockfile`. Never create an npm or yarn lockfile; CI rejects anything but one pnpm lockfile per package |
