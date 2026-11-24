# Test Execution Guide

How to run the test suites, what CI runs, and how the failure baselines work. How to write a
test is in [TESTING_GUIDELINES.md](TESTING_GUIDELINES.md). Frontend command details are in
[docs/frontend/testing/TESTING_COMMANDS.md](../frontend/testing/TESTING_COMMANDS.md).

Do not hardcode counts. Get live ones:

```bash
python scripts/check_doc_counts.py                       # test files / functions, static
python -m pytest --collect-only -q -q | tail -1          # collected (two -q: pytest.ini adds --verbose)
python -m pytest -m slow --collect-only -q -q | tail -1  # for any marker expression
```

## Setup

```bash
uv venv --python-preference only-managed && source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install -e '.[dev]'                  # pytest, pytest-asyncio, pytest-cov, pytest-timeout, httpx2
cd vendor/auralis-dsp && maturin develop    # the Rust DSP module; fingerprint tests need it
pnpm --dir auralis-web/frontend install --frozen-lockfile
```

Without `auralis_dsp`, every fingerprint test fails and every `importorskip("auralis_dsp")`
test skips. FFmpeg must be on `PATH` for the decode and probe paths.

`pytest.ini` puts `auralis-web/backend` on `pythonpath`, so backend modules import as
top-level names (`from main import app`, `from core...`). Run pytest from the repository root.

## Inner loop: scope first, widen once

The backend suite takes tens of minutes. Run the directory or file you touched.

```bash
python -m pytest -q -m "not slow" tests/auralis/dsp          # a domain
python -m pytest -q tests/backend/test_albums_api.py         # a file
python -m pytest tests/path.py::test_name -vv -s             # one test, with output
python -m pytest -q --lf                                     # re-run last failures
python -m pytest -q -x --durations=15 tests/auralis/player   # stop at first failure, show slow tests
```

`-q` keeps passes as dots; `-v` (already in `addopts`) lists every test name, so the flag
matters at scale. `tests/` layout: `auralis/` (engine, mirrors the package tree), `backend/`
(routers, services, WebSocket), `integration/`, `boundaries/`, `regression/`, `security/`,
`concurrency/`, `edge_cases/`, `audio/`, `input_media/`, `vendor/` (Rust DSP via PyO3),
`performance/`, `load_stress/`, `stress/`, `utils/`.

Never run a broad scope by reflex: a single large `tests/` subdirectory can exhaust memory
(`tests/backend` boots the real FastAPI app per `client` fixture).

### The two files that hang

`tests/backend/test_system_api.py` and `tests/concurrency/test_thread_safety.py` have hung on
whole-file runs (unbounded waits on a barrier, and unread WebSocket frames wedging the next
test). Both have since been fixed and the per-push CI job runs them, but the nightly job
(`slow-tests.yml`) and the documented whole-suite command still exclude them. If you run either
locally, bound it:

```bash
python -m pytest -q --timeout=60 tests/concurrency/test_thread_safety.py
```

### Whole backend suite

```bash
python -m pytest -q -m "not slow" \
  --ignore=tests/backend/test_system_api.py \
  --ignore=tests/concurrency/test_thread_safety.py
```

Per-test timeout is 300 s (`timeout` in `pytest.ini`); override with `--timeout=N`.

## Environment hazards

- **Backend tests and the real library.** The default library is `~/.auralis/library.db`.
  The `client` fixture in `tests/backend/conftest.py` and the autouse fixtures in
  `tests/integration/conftest.py` redirect it to a throwaway database and a throwaway
  `.25d` fingerprint store (`tests/app_isolation.py`). A test that boots `main.app` any other
  way must request `_isolated_library_db` and `_isolated_fingerprint_store` itself. When in
  doubt, run with a scratch home, which isolates everything under `~/.auralis`:

  ```bash
  HOME=$(mktemp -d) python -m pytest -q tests/backend/test_albums_api.py
  ```

- **Rust DSP tests and `ulimit -v`.** Any test that calls `auralis_dsp` fails spuriously under
  a virtual-memory cap: rayon cannot reserve thread-stack address space and raises
  `RuntimeError: Rust DSP panic ... ThreadPoolBuildError`. Run those tests uncapped, and do
  not read such failures as a build regression.
- **Local-library tests.** Tests marked `local_library` read a developer's personal music
  library and are skipped unless `AURALIS_LOCAL_LIBRARY_TESTS=1`.
- **BLAS threads.** `np.dot` / `@` over whole tracks leaves OpenBLAS threads spinning after
  `process()`; DSP code uses `einsum` for that reason, and
  `tests/auralis/dsp/test_no_blas_spin_after_process.py` guards it.

## Markers

`pytest.ini` runs with `--strict-markers`, so a marker must be declared there before use.
`python -m pytest --markers` prints the full list. Most markers are descriptive tags; these are
the ones that change what runs:

| Marker | Effect |
|--------|--------|
| `slow` | Excluded from the per-push job (`-m "not slow"`), run by the nightly job (`-m slow`). `tests/conftest.py` adds it to every test under `tests/performance`, `tests/load_stress` and `tests/stress` (`NIGHTLY_ONLY_DIRS`); do not mark those individually. |
| `local_library` | Skipped unless `AURALIS_LOCAL_LIBRARY_TESTS=1`. |
| `integration`, `boundary`, `e2e`, `invariant`, `regression`, `security`, `concurrency`, `performance`, `unit` | Test kind. Useful as `-m` selectors, but coverage of the tag is uneven: select by directory first, and check the marker with `--collect-only` before trusting it to mean "all of that kind". `invariant` and `e2e` tag only a few tests. |
| `fast` | Declared as "under 100 ms"; applied to a handful of files, so `-m fast` is not a complete fast lane. The inner-loop filter is `-m "not slow"`. |

Marker expressions combine with `and`, `or`, `not`:
`-m "boundary and not slow"`, `-m "security or concurrency"`.

## What CI runs

| Workflow | Trigger | Command | Verdict |
|----------|---------|---------|---------|
| `backend-tests.yml`, job `pytest` | push to `master`, PR touching engine/backend/tests | `python -m pytest -q -m "not slow" -p no:randomly --durations=25 --junitxml=pytest-results.xml` | `scripts/check_pytest_baseline.py pytest-results.xml --strict-stale` |
| `backend-tests.yml`, job `gates` | same | the weak-assertion, LOC, breadcrumb and ruff checks | each script's exit code |
| `slow-tests.yml` | nightly 03:17 UTC, manual | `python -m pytest -q -m slow -p no:randomly --timeout=300 --ignore=<the two files> --junitxml=pytest-slow-results.xml` | `check_pytest_baseline.py ... --baseline pytest-slow-baseline.json --strict-stale` |
| `frontend-test.yml` | PR / push touching the frontend | `pnpm run test:ci` | `pnpm run test:baseline -- --strict-stale`, then `pnpm run test:weak:selftest && pnpm run test:weak` |
| `frontend-typecheck.yml` | same | `pnpm run type-check:prod` and `pnpm run type-check` | tsc exit code; both must be clean |
| `path-references.yml` | docs / `.claude` changes | `.claude/commands/_audit-validate.sh` | exit code |

The test step of each test workflow always exits 0 (`|| true`). The baseline step decides the
job. Both baseline gates also fail when the report is missing or collected zero tests, so a
crashed runner cannot pass as green. The per-push job has a 45-minute cap; the nightly one 60.
If a run is cancelled by the cap, read its `--durations` output and fix the slow tests rather
than raising the cap.

CI installs Python 3.14 and the pinned `requirements-lock.txt`; a different interpreter fails to
collect (the codebase relies on PEP 649 deferred annotations).

### Gates you can run locally

```bash
python scripts/check_weak_assertions.py          # tests asserting only `is not None`, or asserting nothing that can fail
python scripts/check_weak_assertions.py --zero   # tests with no assertion at all
python scripts/check_loc_ratchet.py              # 300-line rule and split-target ceilings
python scripts/check_breadcrumbs.py              # history comments, file:LINE anchors
ruff check --select F401,F811,F841 auralis auralis-web/backend scripts tools
.claude/commands/_audit-validate.sh              # doc path references and links
cd auralis-web/frontend && pnpm run test:weak    # frontend weak specs
```

What the rules mean is in [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md).

## Failure baselines

Each suite is a ratchet: a checked-in file lists the tests known to fail, a run fails on any
failure not listed, and the list may shrink but never grow.

| File | Suite | Checker |
|------|-------|---------|
| `pytest-baseline.json` | per-push backend run | `scripts/check_pytest_baseline.py` |
| `pytest-slow-baseline.json` | nightly slow run | `scripts/check_pytest_baseline.py --baseline pytest-slow-baseline.json` |
| `auralis-web/frontend/test-baseline.json` | frontend vitest run | `auralis-web/frontend/scripts/check-test-baseline.mjs` |
| `weak-assertions-baseline.json`, `zero-assertions-baseline.json` | weak/zero-assertion tests | `scripts/check_weak_assertions.py` |
| `auralis-web/frontend/weak-tests-baseline.json` | frontend weak specs | `scripts/check-weak-tests.mjs` |

All of them list entries by test name (`classname::name`, or `path::title`), never by count, so
fixing one test cannot offset breaking another.

The three failure baselines are empty today, so any failure is new. `pytest-baseline.json`'s
`generatedFrom` block records the run the list was last written from, not the current size.

### Stale and phantom entries

`--strict-stale` makes the pytest and frontend checkers fail on a baseline entry that is no
longer valid. Both CI baseline steps pass it.

- **Stale:** a baselined test that ran and passed. Its entry would silently re-permit that exact
  failure. Only tests present in the report count, so a scoped run cannot trip it.
- **Phantom** (pytest checker): an entry naming a test that no longer exists, found statically by
  resolving the node id to a file, class and `def`. It is caught even on a scoped run.

### Verify a run against a baseline

```bash
python -m pytest -q -m "not slow" tests/auralis/dsp --junitxml=/tmp/dsp.xml
python scripts/check_pytest_baseline.py /tmp/dsp.xml            # new failures only
python scripts/check_pytest_baseline.py /tmp/dsp.xml --strict-stale
```

### Regenerate a baseline

Regenerate when a fix makes a baselined test pass; otherwise the entry lingers and re-permits
the failure. Generate backend baselines from a CI artifact, not a local run: a baseline built
against a different interpreter or dependency set reports spurious failures.

```bash
gh run download <run-id> -n pytest-results            # per-push artifact
python scripts/check_pytest_baseline.py pytest-results.xml --update

gh run download <run-id> -n pytest-slow-results       # nightly artifact
python scripts/check_pytest_baseline.py pytest-slow-results.xml \
  --baseline pytest-slow-baseline.json --update
```

The frontend baseline is written locally, and only from a `node_modules` that matches
`pnpm-lock.yaml` (`pnpm run test:baseline:update` first runs `scripts/check-installed-deps.mjs`
and refuses a stale install):

```bash
cd auralis-web/frontend && pnpm run test:ci && pnpm run test:baseline:update
```

The weak-assertion baselines shrink with `python scripts/check_weak_assertions.py --update`
(add `--zero` for the zero-assertion one) and `pnpm run test:weak:update`. Run `--update`
only after strengthening tests, never to absorb a new offender.

## Frontend tests

Run from `auralis-web/frontend/`:

```bash
pnpm run test:memory src/components/player     # scoped, 2 GB heap
pnpm run test:memory                           # whole suite; the plain run can OOM
pnpm run test:run -t "skips to next track"      # by test name
pnpm run test:coverage
pnpm run type-check                            # tsc --noEmit, tests included
```

Vitest runs in `forks` with `maxWorkers: 2` and `jsdom`; `vitest.config.ts` has the settings.
`pnpm run test:ci` writes a JSON report under `test-results/`, the input of the baseline checker.

## Coverage

```bash
python -m pytest -q --cov=auralis --cov-report=term-missing tests/auralis/dsp
python -m pytest -q --cov=auralis --cov-report=html tests/auralis/dsp   # htmlcov/
```

`[tool.coverage.*]` in `pyproject.toml` enables branch coverage and sets the exclusions. There
is no `fail_under`: no threshold is enforced, and coverage does not stand in for assertions
(see [TESTING_GUIDELINES.md](TESTING_GUIDELINES.md)).

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `Unknown pytest.mark.x` collection error | `--strict-markers`: declare the marker in `pytest.ini`. |
| Run never finishes | A hang-prone file, or a test waiting on a thread or socket. Add `--timeout=60` and `-x`. |
| Whole run ends in 0 collected tests | Wrong interpreter; the suite needs Python 3.14. |
| Fingerprint tests fail, `ModuleNotFoundError: auralis_dsp` | Build the Rust module: `cd vendor/auralis-dsp && maturin develop`. |
| Rust DSP tests fail with `ThreadPoolBuildError` | A `ulimit -v` cap is active. Run uncapped. |
| Frontend run dies with heap OOM | Use `pnpm run test:memory`, and scope the path. |
| Baseline step reports a stale entry | The test passes now; regenerate the baseline (above). |
| Baseline step reports a new failure | Not in the list: fix it. Do not add it. |
| Port 8765 busy | `lsof -ti:8765 \| xargs kill -9`. |
