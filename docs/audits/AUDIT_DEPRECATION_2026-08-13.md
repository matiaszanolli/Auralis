# Deprecation Audit — 2026-08-13

**Scope**: Python stdlib/language, NumPy/SciPy/audio libs, FastAPI/Pydantic/SQLAlchemy,
React/Redux/MUI, Node/npm/build tooling, Rust/PyO3, internal deprecations, config/CI.

**Method**: fresh read of the working tree. Every claim was grep-located, `Read`-confirmed,
and — where the library was the authority — verified against the *installed* package source
in the installed venv (*.venv/lib/python3.14/site-packages/*) or the frontend's *node_modules/*, not from
memory. Two runtime probes were used as positive evidence rather than pattern matching:

- `python -W always::DeprecationWarning` importing the 9 main engine modules and the 10 main
  backend modules — **0 warnings, 0 import failures**.
- scoped `pytest -rw` over `tests/auralis/dsp`, `tests/auralis/analysis`, `tests/auralis/io`
  (395 tests) — **3 warnings total**, all one finding below.

Environment verified as stated: Python **3.14.0** (uv venv), numpy 2.4.6, scipy 1.18.0,
fastapi 0.141.1, pydantic 2.13.4, SQLAlchemy 2.0.51, soundfile 0.14.0, librosa 0.11.0,
pytest 9.0.1, mypy 2.3.0, black 26.5.1, ruff 0.16.1; React 18.3.1, MUI 9.0.1, TS 5.9.3,
Vite 7.3.5, Vitest 4.1.7, RTK 2.11.2, react-redux 9.2.0, pnpm 10.20.0; Rust toolchain
pinned 1.96.0, pyo3 0.23 / numpy-rs 0.23 / ndarray 0.16, `Cargo.lock` tracked.

---

## Executive Summary

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 3 |
| **Total NEW** | **4** |

Additionally **11 candidate findings were suppressed as already-tracked open issues**, and
**14 previously-closed deprecation issues were re-verified as still fixed** (no regressions).

### Headline

**The codebase has no deprecated-API debt of consequence.** This is the cleanest dimension
sweep in the audit series: zero Pydantic V1 syntax, zero SQLAlchemy 1.x `Query` usage, zero
legacy React APIs, zero removed-NumPy aliases, zero PEP 594 dead-battery imports, zero
`datetime.utcnow()`, zero `@app.on_event`. The migrations that earlier audits opened
(#4528/#4529/#4915/#4918/#3484/#2931/#2933/#2938) all completed and none regressed.

What remains is **residue around the edges of those completed migrations** — config blocks
and CI pins that still describe the pre-migration world:

1. `backend-tests.yml` still hard-pins `pytest==9.0.1` on a rationale that #4529 deleted the
   cause of, re-imposing in CI the exact ceiling that issue lifted in the manifests (**MEDIUM**).
2. `[tool.mutmut]` targets *auralis/library/cache.py*, deleted in #4915 (**LOW**).
3. Three test functions `return True`, emitting `PytestReturnNotNoneWarning` on every run —
   pytest has announced this becomes an error (**LOW**).
4. `tempfile.mktemp()` at two test sites (**LOW**).

### Recommended migration order

1. **DEP-CFG-01** first — it is the only finding that changes what CI actually verifies, and
   fixing it costs one line plus a comment rewrite.
2. **DEP-PY-01** next — it is the pre-condition for a clean `filterwarnings = error` posture,
   and it is 3 lines.
3. **DEP-INT-01** and **DEP-PY-02** opportunistically.

### Dependency upgrade roadmap

| Package | Current | Action | Blocked by |
|---|---|---|---|
| pytest | CI 9.0.1 / local 9.0.1, floor `>=9.0.1` | Let CI float to 9.1.x — collection already verified green on 9.1.1 (#4529) | DEP-CFG-01 |
| pyo3 / numpy-rs | 0.23 + `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` | **Hold.** Known-blocked, not stale | numpy-rs 0.29 ABI v2 vs NumPy 2.3.x — documented in `vendor/auralis-dsp/.cargo/config.toml`; reproduces on 3.13 too, so not a Python-version problem |
| dev-extra floors (mypy/black/isort/pylint/pre-commit) | 2021–2022-era floors | Raise to match the tool configs in the same file | Already tracked: **#4336** |
| Everything else | current | No action | — |

### Migration effort

| Finding | Call sites | Effort |
|---|---|---|
| DEP-CFG-01 | 1 workflow line + 1 comment block | Small |
| DEP-INT-01 | 1 config block (5 lines) | Small |
| DEP-PY-01 | 3 functions, 1 file | Small |
| DEP-PY-02 | 2 lines, 2 files | Small |

---

## Findings

### MEDIUM

#### DEP-CFG-01: `backend-tests.yml` hard-pins `pytest==9.0.1` on a rationale #4529 already invalidated

- **Severity**: MEDIUM
- **Dimension**: Config/CI
- **Location**: `.github/workflows/backend-tests.yml:86-90`
- **Status**: NEW (residue of closed #4529)
- **Deprecated API**: the legacy `pytest_ignore_collect(path, config)` / `py.path.local` hook
  signature, removed in pytest 9.1
- **Deprecated Since**: pytest 8.x (deprecated), pytest 9.1 (removed)
- **Removal Version**: pytest 9.1 — already shipped
- **Replacement**: `pytest_ignore_collect(collection_path, config)`; here, no hook at all —
  it was deleted outright
- **Affected Files**: 1 (`.github/workflows/backend-tests.yml`); diverges from 2 others
  (`pyproject.toml`, `pytest.ini`)

**Evidence** — the workflow still asserts the blocker as present tense:

```yaml
          # pytest MUST stay at 9.0.x: 9.1 removed the legacy
          # pytest_ignore_collect(path, config) hook signature that
          # tests/conftest.py still uses, which crashes collection entirely.
          pip install 'pytest==9.0.1' pytest-asyncio pytest-timeout httpx2
```

The premise is false. `tests/conftest.py` has **no** `pytest_ignore_collect` hook — the only
occurrences repo-wide are a historical comment in that file and a guard test that asserts the
hook must not come back with the old signature:

```
tests/conftest.py:34:# the legacy `pytest_ignore_collect(path, config)` / `py.path.local` signature
tests/test_conftest_hooks_4529.py:80:    """If `pytest_ignore_collect` comes back, it must take `collection_path`."""
```

Both manifests were updated when #4529 closed and now say the opposite of the workflow:

- `pyproject.toml:80-87` — *"Upper bound REMOVED in #4529 … Verified: `pytest --collect-only tests/` succeeds on 9.1.1. The floor mirrors minversion in pytest.ini."* → `"pytest>=9.0.1"`
- `pytest.ini:104-112` — *"the ceiling has been lifted. Keep this in sync with pyproject.toml."* → `minversion = 9.0.1`

The workflow is the one file that did not get the memo, and it re-imposes the lifted ceiling
in the only place that gates merges.

**Impact / Risk**: CI validates the suite against a pytest that no contributor gets. A fresh
`uv pip install -e '.[dev]'` resolves 9.1.x (the floor is `>=9.0.1`), so a behaviour difference
between 9.0 and 9.1 — new warnings-to-errors, marker strictness, collection changes — lands as
"green in CI, red locally" or the reverse, with no signal pointing at the version skew. The
false comment is the more durable cost: it is the first thing the next person reads, and it
tells them a migration that is finished is still blocking. This repo has already lost time to
the pytest floor twice (#4559, #4529); a stale ceiling is how it happens a third time.

**Migration Path**:
1. Drop the exact pin so CI takes the manifest's floor:
   `pip install pytest pytest-asyncio pytest-timeout httpx2` (or `'pytest>=9.0.1'` to mirror
   `pyproject.toml` explicitly).
2. Replace the comment with the current fact — floor is `>=9.0.1`, mirroring `pytest.ini`'s
   `minversion`; the 9.1 blockers (legacy hook + 4 undeclared markers) were cleared in #4529.
3. Confirm the run still collects (`pytest --collect-only tests/` on 9.1.x) and that
   `check_pytest_baseline.py` reports the same collected total; regenerate
   `pytest-baseline.json` from that CI artifact if the count moves.

**Effort**: Small (1 line + comment).

---

### LOW

#### DEP-INT-01: `[tool.mutmut]` targets *auralis/library/cache.py*, deleted in #4915

- **Severity**: LOW
- **Dimension**: Internal / Config
- **Location**: `pyproject.toml:159-163`
- **Status**: NEW
- **Deprecated API**: *auralis/library/cache.py* — the `LibraryManager` cache layer
- **Deprecated Since**: deprecated across #4314 / #4619; deleted in **#4915**
- **Removal Version**: already removed
- **Replacement**: none — `LibraryDatabase` + `repositories/` carry no equivalent cache module
- **Affected Files**: 1

**Evidence**:

```toml
[tool.mutmut]
paths_to_mutate = "auralis/library/cache.py"
tests_dir = "tests/mutation/"
runner = "python -m pytest -x --tb=short"
```

Three independent confirmations that this block is dead:

```
$ ls auralis/library/cache.py
ls: cannot access 'auralis/library/cache.py': No such file or directory
$ ls auralis/library/caching/
__init__.py            # empty package, per the Retired Architecture table
$ ls tests/mutation
__init__.py            # no mutation tests exist
```

`mutmut` is also absent from `[project.optional-dependencies].dev` and from
`requirements.txt`, so nothing can execute this config even if the path existed.

**Impact / Risk**: No runtime impact — `[tool.*]` blocks are inert to anything that does not
read them. The cost is that `pyproject.toml` advertises a mutation-testing setup the project
does not have, aimed at a file the project deleted. A reader auditing test rigour sees a
configured mutation suite; running it produces nothing. This is the same class of decorative
config that #4640 removed from `vitest.config.ts` (coverage `thresholds` that nothing
evaluated) — the project has already decided that a config implying a gate it does not have is
worse than no numbers.

**Migration Path**: Delete the `[tool.mutmut]` block and `tests/mutation/__init__.py`. If
mutation testing is wanted, reintroduce both against a live target (a repository module, or
`auralis-web/backend/core/chunk_boundaries.py`) and add `mutmut` to the `dev` extra in the
same change.

**Effort**: Small.

---

#### DEP-PY-01: Three collected tests `return True`, emitting `PytestReturnNotNoneWarning` on every run

- **Severity**: LOW
- **Dimension**: Python Stdlib / test tooling
- **Location**: `tests/auralis/analysis/test_fingerprint_integration.py:149`, `:207`, `:257`
- **Status**: NEW
- **Deprecated API**: returning a non-`None` value from a collected test function
- **Deprecated Since**: pytest 7.2 (warning); the removal is announced in the pytest docs
  linked by the warning text itself
- **Removal Version**: not yet dated — pytest states it will become an error in a future release
- **Replacement**: `assert`, or simply drop the trailing `return`
- **Affected Files**: 1 file, 3 functions

**Evidence** — reproduced, not inferred. `pytest -rw tests/auralis/analysis tests/auralis/io`:

```
tests/auralis/analysis/test_fingerprint_integration.py::test_target_generation
  /mnt/data/src/matchering/.venv/lib/python3.14/site-packages/_pytest/python.py:170:
  PytestReturnNotNoneWarning: Test functions should return None, but
  tests/auralis/analysis/test_fingerprint_integration.py::test_target_generation
  returned <class 'bool'>.
  Did you mean to use `assert` instead of `return`?
```

Emission site, `_pytest/python.py:166-176` — a `PytestWarning`, not yet an error:

```python
    result = testfunction(**testargs)
    if hasattr(result, "__await__") or hasattr(result, "__aiter__"):
        async_fail(pyfuncitem.nodeid)
    elif result is not None:
        warnings.warn(PytestReturnNotNoneWarning(...))
```

An AST sweep of all 519 test files found 19 test-named functions with a direct non-`None`
return; 13 are `@pytest.fixture`-decorated (never collected as tests), 3 are methods of
non-`Test*` classes (`YinValidator`, `HpssValidator` — not collected under
`python_classes = Test*`), leaving exactly these 3. That matches the observed warning count
of 3, so the scope is closed.

The three `return True` statements are vestiges of the script-style `main()` runner at the
bottom of the file (`sys.exit(main())`). They are **not** a coverage gap — all three functions
carry real assertions (`assert "fingerprint" in profile`, `assert processed.shape ==
audio.shape`, `assert not np.isnan(processed).any()`, …), so this is purely the deprecation.

**Impact / Risk**: Today, three lines of recurring noise in every warnings summary — which
matters more than usual here, because #4559 deliberately removed `--disable-warnings` so that
first-party warnings would be visible; this is the only first-party warning left, and it is
the one thing standing between the project and a `filterwarnings = error` ratchet on its own
code. When pytest promotes it, these three tests hard-fail.

**Migration Path**: Delete the three `return True` statements (the functions already assert).
Optionally then add `error::pytest.PytestReturnNotNoneWarning` to `pytest.ini`'s
`filterwarnings` so a fourth one cannot reappear.

**Effort**: Small (3 lines).

---

#### DEP-PY-02: `tempfile.mktemp()` at two test sites

- **Severity**: LOW
- **Dimension**: Python Stdlib
- **Location**: `tests/edge_cases/test_filesystem_errors.py:594`, `tests/integration/test_e2e_workflows.py:308`
- **Status**: NEW
- **Deprecated API**: `tempfile.mktemp()`
- **Deprecated Since**: Python **2.3** — the longest-standing deprecation in the stdlib
- **Removal Version**: not announced (kept for compatibility), but flagged as a security
  hazard in the CPython docs
- **Replacement**: `tempfile.NamedTemporaryFile(delete=False)`, `tempfile.mkstemp()`, or —
  idiomatic for this suite — the `tmp_path` fixture
- **Affected Files**: 2 (test-only; **0** production call sites)

**Evidence**:

```
tests/edge_cases/test_filesystem_errors.py:594:        temp_db_path = tempfile.mktemp(suffix='.db')
tests/integration/test_e2e_workflows.py:308:    temp_output = tempfile.mktemp(suffix=".wav")
```

**Impact / Risk**: `mktemp()` returns a name without creating the file, leaving a
time-of-check/time-of-use window between the name being chosen and the test opening it. On a
developer machine the practical risk is low; the real cost is that two tests write outside
pytest's per-test `tmp_path`, so a crashed run leaks files into the system temp directory
instead of the tmp-dir rotation, and parallel runs of the same test can collide on a name.

**Migration Path**: Replace both with the `tmp_path` fixture —
`temp_db_path = tmp_path / "test.db"` / `temp_output = tmp_path / "out.wav"` — which also
removes the manual cleanup those two tests currently carry. If a bare path string is genuinely
needed, `tempfile.mkstemp()` returns `(fd, path)` with the file already created.

**Effort**: Small (2 lines).

---

## Deduped — Existing Open Issues, Not Re-Reported

Each was independently rediscovered during this sweep and confirmed still present, then
suppressed because an open issue already covers it.

| Candidate found | Existing | Verified still present |
|---|---|---|
| `library_manager` accept-and-drop parameter on `QueueController.__init__` / `EnhancedAudioPlayer.__init__` for a class deleted in #4915 (118 name occurrences repo-wide) | **#4312** | Yes — `auralis/player/queue_controller.py:31`, `auralis/player/enhanced_audio_player.py:76` |
| `@types/uuid@10` redundant next to `uuid@14` (which ships its own `types`), and neither imported anywhere in `src/` | **#4955** | Yes — both still in `dependencies`; `grep -rn uuid src/` returns 0 non-test hits |
| `engines` declared only at the repo root; `auralis-web/frontend/package.json` and `desktop/package.json` have none | **#4952** | Yes — root has `node>=24.0.0`, the other two have `engines: None` |
| `dev` extra floors (`mypy>=0.950`, `black>=22.0.0`, `isort>=5.10.0`, `pylint>=2.14.0`, `pre-commit>=2.17.0`, `pytest-asyncio>=0.17.0`) contradict `[tool.mypy] python_version = "3.14"` and `[tool.black] target-version = ["py314"]` in the same file | **#4336** | Yes — `pyproject.toml:88-104` |
| `dtolnay/rust-toolchain@master` — mutable branch ref in 4 workflow jobs | **#4868** | Yes — `build-release.yml:120,277,410`, `rust-audit.yml:51` |
| Node built-ins imported without the `node:` prefix (`desktop/main.js:4-6,281`, `vite.config.mts:3-4`) | **#4591** | Yes |
| Legacy pytest `tmpdir` / `.fspath` in the test tree (109 hits) | **#4624** | Yes |
| `asyncio.get_event_loop_policy()` — deprecated in 3.14, slated for removal in 3.16 — in test fixtures | **#4332** | Yes — `tests/backend/conftest.py:55`, `tests/integration/test_phase4_player_workflow.py:141` (2 sites, test-only) |
| `edge_cases` marker declared in `pytest.ini` and self-labelled deprecated | **#4337** | Yes |
| Installed venv has drifted off the pinned manifest (numpy 2.4.6 vs `==2.3.5`, scipy 1.18.0 vs `==1.16.3`, fastapi 0.141.1 vs `==0.122.0`, soundfile 0.14.0 vs `==0.13.1`, SQLAlchemy 2.0.51 vs `==2.0.44`, +3 more) | **#4871** | Yes — this is that issue's exact thesis |
| `python-dotenv` pin diverges between the two manifests | **#4948** | Yes |

---

## Regression Checks — Previously Closed, Confirmed Still Fixed

No regressions found. Each closed issue's fix was re-verified against current source.

| Closed issue | Check performed | Result |
|---|---|---|
| **#4915** LibraryManager + cache layer deleted | `ls auralis/library/cache.py`, `auralis/library/caching/` | Gone; `caching/` is an empty package. `auralis/library/__init__.py` exports only `LibraryDatabase` |
| **#4529** pytest legacy hook + unbounded floor | `grep pytest_ignore_collect tests/conftest.py` | Hook gone; only a historical comment + guard test `test_conftest_hooks_4529.py` remain |
| **#4957** `asyncio.iscoroutinefunction` (3.14 deprecation) | repo-wide grep | 0 hits. `routers/dependencies.py:182` correctly uses `inspect.iscoroutinefunction` |
| **#2931** `sessionmaker(bind=engine)` | grep all 5 call sites | All use the 2.0 positional form: `sessionmaker(self.engine)` |
| **#2933** / **#3484** MUI Grid v1 `item`/`xs` props, *Unstable_Grid2* | grep all `<Grid` usage | All migrated — `import Grid2 from '@mui/material/Grid'` with `size={{...}}`. *Unstable_Grid2* has 0 hits |
| **#2938** PyO3 `&PyArray` unbound refs | read `vendor/auralis-dsp/src/py_bindings.rs` | Modern 0.23 API throughout: `PyReadonlyArray1/2`, `Bound<'_, PyModule>`, `into_pyarray(py).unbind()` |
| **#2932** `typing.Deque` | repo-wide grep | 0 hits |
| **#4959** legacy PEP 585/604 generics in `scripts/` | grep `scripts/` | 0 hits |
| **#4904** `.pre-commit-config.yaml` 2023 toolchain | read config | Current: black 26.5.1, isort 8.0.1, mypy v2.3.0, pylint v4.0.6, pre-commit-hooks v6.0.0 |
| **#4886** actions pinned to node20-runtime majors | read all 7 workflows | `checkout@v6`, `setup-python@v6`, `setup-node@v6`, `upload-artifact@v7`, `download-artifact@v8`, `pnpm/action-setup@v6` |
| **#4531** `Cargo.lock` gitignored, no toolchain pin | `git ls-files vendor/auralis-dsp/` | `Cargo.lock` tracked (`.gitignore:188` negation), `rust-toolchain.toml` pins 1.96.0 |
| **#4623** `substr` / `webkitAudioContext` | grep `src/`, `desktop/` | 0 live `.substr(`; `ScriptProcessorNode` survives only as the documented AudioWorklet fallback in `BufferScheduler.ts`, which is the intended design |
| **#4556** `navigator.platform` | grep `src/` | Single guarded read in `keyboardShortcutsService.ts:63`, behind `userAgentData`, with `isMacPlatform.test.ts:82` asserting it is the only site |
| **#2807** `onKeyPress` | grep `src/` | 0 hits |

---

## Clean — Checklist Items Verified With No Findings

### Dimension 1 — Python stdlib & language
- `datetime.utcnow()` / `utcfromtimestamp()` — **0 hits** repo-wide (production *and* tests).
- PEP 594 dead batteries (`audioop`, `aifc`, `sunau`, `cgi`, `telnetlib`, `imghdr`, `pipes`, … 20 modules) — **0 imports**. Notable for an audio codebase: no `audioop`/`aifc`/`sunau`.
- `imp`, `distutils`, `pkg_resources` — 0 imports.
- `asyncio.get_event_loop()` / `set_event_loop()` / `@asyncio.coroutine` — 0 hits in production. `ensure_future`, `asyncio.wait`, `inspect.iscoroutinefunction` all used in their current forms.
- Legacy `typing` generics in production — 8 hits, **all inside docstrings**, none in real annotations; 34 modules use `from __future__ import annotations`.
- `typing.ByteString` / `typing.Text` (removed 3.14) — 0 hits.
- `ast.Num` / `ast.Str` / `ast.Bytes` / `ast.NameConstant` — 0 hits.
- `unittest` legacy aliases (`assertEquals`, `failUnless`, …) — 0 hits.
- `threading` legacy aliases (`setDaemon`, `isAlive`, `setName`) and `daemon` set after `start()` — 0 hits.
- ABCs imported from `collections` instead of `collections.abc` — 0 hits.
- `locale.getdefaultlocale()`, `ssl.PROTOCOL_TLS`, `ssl.wrap_socket`, `configparser.readfp` — 0 hits.
- **Import probe**: 9 engine modules imported under `-W always::DeprecationWarning` → 0 warnings.

### Dimension 2 — NumPy / SciPy / audio
- NumPy 2.x removed aliases (`np.bool`, `np.int`, `np.float`, `np.complex`, `np.object`, `np.str`) — 0 hits (the single grep match is prose in `test_pyproject_dependencies_4528.py` explaining *why* the `numpy>=2.0` floor exists).
- NumPy 2.0 removals (`np.product`, `np.in1d`, `np.row_stack`, `np.NaN`, `np.Inf`, `np.float_`, `np.trapz`, `np.AxisError`, `np.MachAr`, `np.deprecate`, +14 more) — 0 hits.
- `np.core` / `np.compat` private-module access — 0 hits.
- `np.array(..., copy=False)` (raises under NumPy 2) — 0 hits. The 14 `copy=False` matches are all `astype(dtype, copy=False)`, which is unchanged and correct.
- `np.fromstring` — 0 hits (the 2 `fromstring(` matches are `xml.etree.ElementTree.fromstring`).
- `scipy.fftpack`, `scipy.misc` — 0 imports. All FFT goes through `scipy.fft` (`fft`, `ifft`, `rfft`, `rfftfreq`).
- `scipy.signal.hanning`/`hamming`/`blackman` top-level window functions (removed 1.13) — 0 hits; every window import is `from scipy.signal.windows import hann/hamming`.
- `scipy.integrate.simps` / `cumtrapz` / `trapz`, `scipy.interpolate.interp1d` — 0 hits.
- librosa 0.11 — all calls use current keyword-only signatures (`librosa.resample(y, orig_sr=, target_sr=)`, `librosa.load(path, sr=, mono=, duration=)`, `librosa.feature.spectral_centroid(S=, sr=)`).
- soundfile 0.14 — `sf.read`/`sf.write`/`sf.info`/`sf.check_format`/`sf.SoundFile` are all current.

### Dimension 3 — FastAPI / Pydantic / SQLAlchemy
- **Pydantic V1 syntax: 0 occurrences of all 18 patterns checked** — `class Config:`, `.dict()`, `.json()`, `@validator`, `@root_validator`, `parse_obj`, `parse_raw`, `orm_mode`, `schema_extra`, `allow_population_by_field_name`, `min_items`/`max_items`, `regex=`, `const=`, `__fields__`, `parse_obj_as`, `update_forward_refs`, `pydantic.v1`. The 3 `schema_extra` grep hits are the correct V2 `json_schema_extra`, two of them inside `model_config = ConfigDict(...)`.
- `@app.on_event("startup"/"shutdown")` — 0 hits; the app uses a lifespan context manager.
- **SQLAlchemy: 0 occurrences of `session.query(`** anywhere in `auralis/` or `auralis-web/`. Fully 2.0-style: `Base(DeclarativeBase)` in `auralis/library/models/base.py:20`, **163** `mapped_column()` and **178** `Mapped[]` annotations, **0** bare `Column()`.
- `engine.execute()`, `declarative_base()`, `autocommit`, `bulk_save_objects`, `bulk_insert_mappings`, `sessionmaker(bind=)` — 0 hits. The 2 `connection.execute("PRAGMA …")` matches in `auralis/analysis/fingerprint/catalog.py:71-72` are the **stdlib `sqlite3`** API, not SQLAlchemy, and are correct there.
- **Import probe**: 10 backend modules (incl. `main`, `config.app`, `schemas`, 3 routers, `core.chunked_processor`, `ws_handlers.connection`) imported under `-W always::DeprecationWarning` → 0 warnings, 0 failures.

### Dimension 4 — React / Redux / MUI / TypeScript
- `ReactDOM.render`, `hydrate`, `unmountComponentAtNode`, `findDOMNode` — 0 hits.
- Legacy lifecycles, `UNSAFE_*`, legacy context (`contextTypes`/`childContextTypes`), string refs — 0 hits.
- `defaultProps` on function components — 0 hits in `src/` (the matches are a local `defaultProps` object literal spread into `render()` inside one test file, which is unrelated).
- `React.FC` / `React.FunctionComponent` — 0 hits in code (1 mention in a markdown report).
- `propTypes` / `prop-types` — 0 hits.
- `react-dom/test-utils` `act` (deprecated React 18.3) — 0 hits; `act` comes from `react` or `@testing-library/react`.
- Redux: `createStore` — 0 hits; `connect()` HOC — 0 hits; `extraReducers` object-map syntax (removed in RTK 2) — 0 hits; `batch()` — 0 hits.
- MUI 9: `@mui/styles`, `makeStyles`, `withStyles`, `createStyles`, `createMuiTheme`, `withWidth`, `experimentalStyled`, `adaptV4Theme`, `unstable_*`, *@mui/material/styles/\** deep imports — **0 hits**. Cross-checked the other direction: enumerated every `@deprecated` symbol in the installed `@mui/material@9.0.1` type surface (`darkScrollbar`, `StandardProps`, the *@mui/material/utils* `createSvgIcon` re-export, `ThemeProviderWithVars`, `NativeSelectInput`) — **none is imported by `src/`**.
- `components=` / `componentsProps=` / `TransitionComponent=` / `InputProps=` / `SelectProps=` (superseded by `slots`/`slotProps`) — 0 hits.
- `Grid2` is a **local import alias** for `@mui/material/Grid` (`import Grid2 from '@mui/material/Grid'`), used with the modern `size={{...}}` API. Not the deprecated *Unstable_Grid2* — #3484 is genuinely closed. The alias name is a cosmetic leftover, below the reporting bar.
- tsconfig: `moduleResolution: "bundler"`; none of the TS 5.5-removed options (`importsNotUsedAsValues`, `preserveValueImports`, `suppressImplicitAnyIndexErrors`, `charset`, `keyofStringsOnly`, `out`, `reactNamespace`) present.
- `react-router-dom` — no router is mounted in `src/`; no v5 APIs (`<Switch>`, `useHistory`, `Route component=`) present.
- Testing Library — no removed APIs. `waitForElement` in `auralis-web/frontend/src/test/utils/test-helpers.ts` is a **project-local helper**, not the removed dom-testing-library export.

### Dimension 5 — Node / npm / build tools
- A node_modules scan for the npm `deprecated` field across all direct **and** transitive packages: **0 deprecated packages installed**.
- Vitest config already migrated for Vitest 4 (#3488): `poolOptions` → top-level, `maxForks` → `maxWorkers`, `restoreAllMocks` removed, `snapshotFormat.escapeControlCharacters` dropped. No v3 keys remain.
- Vite 7 config uses no deprecated options.
- Deprecated Node APIs (`fs.exists`, `url.parse`, `querystring`) — 0 hits.
- ESLint — no config file exists in the repo, so the flat-config migration is not applicable (there is nothing to migrate).
- Electron 43 (`desktop/main.js`): no `remote` module, no `enableRemoteModule`, no `allowRendererProcessReuse`, no `registerFileProtocol`, no `new-window` event. Uses `app.whenReady()`, `contextBridge`, and `nodeIntegration: false` + `contextIsolation: true`.

### Dimension 6 — Rust / PyO3 / Cargo
- `py_bindings.rs` uses current pyo3 0.23 idioms throughout: `Bound<'_, PyModule>`, `PyReadonlyArray1/2`, `into_pyarray(py).unbind()`, `#[pyo3(signature = ...)]`. **No** `IntoPy`/`ToPyObject`/`into_py()`/`to_object()` (the traits pyo3 0.23 deprecates in favour of `IntoPyObject`), and no `Python::acquire_gil`.
- GIL is released for every long compute — all 11 exported functions wrap their kernel in `py.allow_threads(...)`, which is the correct 0.23 spelling (`Python::detach` is a later rename, not applicable here).
- No deprecated Rust std APIs (`mem::uninitialized`, `try!`, `std::*::MAX` module constants, `trim_left`/`trim_right`).
- `Cargo.lock` is **tracked** (explicit `!vendor/auralis-dsp/Cargo.lock` negation at `.gitignore:188`), and `rust-toolchain.toml` pins 1.96.0 — the conditions that hid the ndarray 0.15/0.16 conflict are closed.
- Edition 2021 (vs. the available 2024) is a version lag, **not a deprecation** — Rust editions are supported indefinitely. Not reported.
- **pyo3 / numpy-rs 0.23 is a known-blocked upgrade, not a stale pin.** `vendor/auralis-dsp/.cargo/config.toml` documents the full reasoning at length: 0.29 compiles but every array-accepting call then raises `TypeError: 'ndarray' object is not an instance of 'ndarray'` because numpy-rs 0.29 targets NumPy ABI v2, incompatible with the pinned NumPy 2.3.x — and it reproduces on 3.13, so it is a numpy-rs problem, not a Python-version one. The abi3-forward-compat side effect (limited-API build, `#[cfg(not(Py_LIMITED_API))]` code silently dropped) is separately documented and CI-asserted (#4911). Recorded here as context only.

### Dimension 7 — Internal deprecations
- `warnings.warn(...)` — **0 emission sites** in production code. The 2 `DeprecationWarning` grep hits are historical comments describing the now-deleted `LibraryManager` warning.
- No `@deprecated`-decorated internal API has a live caller. The 46 `deprecated`/`legacy` string matches are all historical comments and `#4619`/`#4618`/`#4915` migration notes — verified by reading the 13 most substantive.
- Retired-architecture references (`LibraryManager`, categorical mastering branches, `parallel_processor`, `EnhancementContext`, legacy `core/config.py`) appear only in comments and docstrings, per the Retired Architecture table. Not reported.

### Dimension 8 — Config & CI
- No *setup.py* / *setup.cfg* (correctly consolidated into `pyproject.toml`).
- No *Dockerfile* or container config has reappeared.
- `pyproject.toml` `requires-python = ">=3.14"` matches `.python-version` (`3.14`) — the old gap is closed.
- Version consistency: `auralis/version.py` `1.5.1` == `pyproject.toml` `version = "1.5.1"` == `desktop/package.json` `1.5.1`.
- All 7 workflows pin Python `3.14`; none lowers it.
- `pnpm/action-setup@v6` carries **no** `version:` input in any of the 6 jobs that use it, and both `frontend-test.yml:42-47` and `frontend-typecheck.yml:36-38` carry the comment explaining why. No regression.
- **Baseline gates verified live**, not assumed:
  - `scripts/check_pytest_baseline.py:66-69` — `if total == 0: _die("pytest reported 0 collected tests — treating as a failed run.")`, plus a missing-report exit at `:46`. Still invoked at `backend-tests.yml:105`. `pytest-baseline.json` now **exists** (50 KB, dated 2026-08-12) — the #4739 blocker is cleared.
  - `auralis-web/frontend/scripts/check-test-baseline.mjs:56-58` — `if (!parsed.numTotalTests) { …; process.exit(1); }`, plus missing/unparseable-report exits at `:42`, `:49`, `:53`. Still invoked via `pnpm run test:baseline` at `frontend-test.yml:69`.
  - Both test steps still `|| true` / `|| true`-equivalent by design, with the baseline step deciding the job. A crashed runner cannot pass as green.
- Guard workflows all present and wired: `lockfile-guard.yml`, `requirements-pin-guard.yml`, `rust-audit.yml`, `.github/scripts/check_pyproject_deps.py`.
- `pytest.ini`: `minversion = 9.0.1` in sync with the `pyproject.toml` floor (the divergence is in CI — see DEP-CFG-01), `--strict-markers` + `--strict-config` on, all markers declared, `filterwarnings` retains `default::DeprecationWarning` with narrowly-scoped third-party `ignore::` entries and **no** blanket `--disable-warnings` (#4559 holds).
- `mypy` config uses no deprecated options; `python_version = "3.14"`. `black` `target-version = ["py314"]`. No deprecated `ruff` rules configured.

---

## Next Step

```
/audit-publish docs/audits/AUDIT_DEPRECATION_2026-08-13.md
```
