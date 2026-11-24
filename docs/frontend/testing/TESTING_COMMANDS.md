# Frontend Testing Commands - Cheat Sheet

Quick reference for running the frontend (Vitest) tests. pnpm is the only
supported package manager; run everything from `auralis-web/frontend/`. Every
`pnpm run <name>` below is a script in `auralis-web/frontend/package.json`;
commands that pass extra flags (`--reporter`, `-t`, `-u`, `--changed`) are
Vitest CLI options forwarded through `pnpm test`.

---

## Basic Commands

```bash
cd auralis-web/frontend

pnpm test                       # watch mode (same as test:watch)
pnpm run test:run               # one pass, then exit
pnpm run test:memory            # one pass with a 2GB heap: use this for the whole suite
pnpm run test:ui                # Vitest UI
pnpm run test:coverage          # coverage report in coverage/
pnpm run test:coverage:memory   # the same with the 2GB heap
pnpm run type-check             # tsc --noEmit over every source, tests included
pnpm run type-check:prod        # tsc --noEmit -p tsconfig.build.json (shipped code only)
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

Memory diagnostics: `pnpm run test:memory:failsafe` (`scripts/memory-test-failsafe.js`), which runs
tests by category under a heap limit. Pass options after `--`, for example
`pnpm run test:memory:failsafe -- --category library --max-heap 1024`.

---

## CI Gates

`.github/workflows/frontend-test.yml` and `frontend-typecheck.yml` run these;
reproduce them locally before pushing:

```bash
pnpm run test:ci                                    # 2GB heap; writes test-results/ci-results.json
pnpm run test:baseline -- --strict-stale            # judge the report against test-baseline.json
pnpm run test:weak:selftest && pnpm run test:weak   # weak-assertion gate
pnpm run type-check:prod                            # shipped code must be clean
pnpm run type-check                                 # tests included
```

The test step itself never fails the job; the baseline step decides.

- **Test baseline** (`test-baseline.json`, checked by `scripts/check-test-baseline.mjs`). It
  lists known-failing specs and its `failures` array is empty, so any failing test is new and
  fails the job. The gate also fails when a report is missing, when the run collected under 90 %
  of the baseline's test count, and, with `--strict-stale`, on baseline entries that now pass.
  After fixing a failing test, regenerate it with
  `pnpm run test:ci && pnpm run test:baseline:update`.
- **Weak-spec gate** (`scripts/check-weak-tests.mjs`, baseline `weak-tests-baseline.json`). It
  lists specs with no assertion (`zero`), only presence checks such as `toBeDefined` (`weak`), or
  an assertion inside an `if` with no `else` (`conditional`). The baseline may shrink but never
  grow; `pnpm run test:weak -- --list` prints every current offender and
  `pnpm run test:weak:update` rewrites the baseline after you strengthen a spec.
- **Type checks** (`frontend-typecheck.yml`) have no baseline: `type-check:prod` and `type-check`
  must both be clean.

---

## Test Layout

```
src/
├── **/__tests__/, *.test.ts(x)   # unit/component tests next to the code
├── test/
│   ├── setup.ts                  # global setup: MSW server, WebSocketContext mock, browser stubs
│   ├── test-utils.tsx            # render() with providers (Redux, Query, Theme, Toast,
│   │                             #   PlaybackSession): import from here
│   ├── mocks/                    # MSW server.ts, handlers.ts, mockData.ts, websocket.ts
│   ├── utils/                    # test-helpers.ts, TestProviders.tsx
│   └── README.md                 # how to write tests
└── tests/integration/            # library-management/, websocket-realtime/
```

Vitest is configured in `vitest.config.ts` (jsdom, `forks` pool, 2 workers). A REST call to
`/api/` with no MSW handler fails the test, so add a handler in `src/test/mocks/handlers.ts` or
`server.use(...)` in the spec.

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
