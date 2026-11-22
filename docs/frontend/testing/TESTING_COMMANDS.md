# Frontend Testing Commands - Cheat Sheet

Quick reference for running the frontend (Vitest) tests. pnpm is the only
supported package manager (#4357); run everything from `auralis-web/frontend/`.
Every command below maps to a script in `auralis-web/frontend/package.json`.

---

## Basic Commands

```bash
cd auralis-web/frontend

pnpm test                 # watch mode
pnpm run test:run         # one pass, then exit
pnpm run test:memory      # one pass with a 2GB heap: use this for the whole suite
pnpm run test:ui          # Vitest UI
pnpm run test:coverage    # coverage report in coverage/
pnpm run type-check       # tsc --noEmit
```

Running the whole suite without `test:memory` can OOM. In the inner loop,
scope to the files or directories you touched.

---

## Running Specific Tests

Vitest filters by a positional path substring (there is no Jest-style
`--testPathPattern`), and by test name with `-t`:

```bash
pnpm run test:memory src/components/player       # a directory
pnpm run test:memory Sidebar.test.tsx            # files whose path contains this
pnpm test -t "skips to next track"               # tests whose name matches
pnpm run test:library                            # src/tests/integration/library-management/
pnpm run test:websocket                          # src/tests/integration/websocket-realtime/
pnpm run test:integration                        # src/tests/integration/ (4GB heap)
pnpm test --changed                              # files changed since the last commit
```

---

## Debugging

```bash
pnpm test Sidebar.test.tsx --reporter=verbose
pnpm test --no-file-parallelism     # run files one at a time
pnpm test --maxConcurrency=5        # cap concurrent tests per file
pnpm test --inspect                 # attach a Node debugger
pnpm test -u                        # update snapshots
pnpm exec vitest --clearCache       # clear Vitest's cache
```

Memory diagnostics: `pnpm run test:memory:failsafe` (`scripts/memory-test-failsafe.js`).

---

## CI Gates

`.github/workflows/frontend-test.yml` runs these; reproduce them locally
before pushing:

```bash
pnpm run test:ci                              # writes the JSON report
pnpm run test:baseline -- --strict-stale      # judge it against test-baseline.json
pnpm run test:weak:selftest && pnpm run test:weak   # weak-assertion gate
pnpm run type-check:prod                      # frontend-typecheck.yml
```

`test-baseline.json` is empty, so any failure is new. After fixing a failing
test, regenerate it with `pnpm run test:ci && pnpm run test:baseline:update`.

---

## Test Layout

```
src/
├── **/__tests__/, *.test.ts(x)   # unit/component tests next to the code
├── test/
│   ├── setup.ts                  # global setup (MSW server, context auto-mocks)
│   ├── test-utils.tsx            # render() with providers — import from here
│   ├── mocks/                    # MSW server.ts, handlers.ts, mockData.ts, websocket.ts
│   └── README.md                 # how to write tests
└── tests/integration/            # library-management/, websocket-realtime/
```

Vitest is configured in `vitest.config.ts`.

---

## Setup (New Developer)

```bash
cd auralis-web/frontend
pnpm install --frozen-lockfile
pnpm run test:memory src/test     # smoke-test the harness
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Out of memory | `pnpm run test:memory` (2GB heap), or scope to a directory |
| Test times out | Pass `{ timeout: 5000 }` to `waitFor`, or check for an unresolved MSW request |
| Port 3000 busy | `lsof -ti:3000 \| xargs kill -9` |
| Stale results | `pnpm exec vitest --clearCache` |

---

## Further Reading

- `src/test/README.md` — writing tests, mocks and utilities
- `docs/development/TESTING_GUIDELINES.md` — project testing rules
- Vitest: https://vitest.dev/ · Testing Library: https://testing-library.com/docs/react-testing-library/intro/ · MSW: https://mswjs.io/docs/
