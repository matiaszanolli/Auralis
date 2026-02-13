# Deprecation Audit

Audit the entire Auralis codebase for deprecated APIs, libraries, patterns, and language features across Python, TypeScript/React, Rust, and all third-party dependencies. Then create GitHub issues for every new confirmed finding.

## Scope

This audit covers ALL layers for deprecation issues:

- **Python engine**: `auralis/` — stdlib, NumPy, SciPy, FFmpeg bindings
- **Backend**: `auralis-web/backend/` — FastAPI, Pydantic, SQLAlchemy, Uvicorn
- **Frontend**: `auralis-web/frontend/` — React, Redux, MUI, Vite, TypeScript
- **Rust DSP**: `vendor/auralis-dsp/` — PyO3, Rust crates
- **Desktop**: `desktop/` — Electron
- **Config**: `pyproject.toml`, `requirements.txt`, `package.json`, `Cargo.toml`, `tsconfig.json`, CI/CD files
- **Tests**: `tests/` — deprecated test patterns, assertion styles

## Severity Definitions

| Severity | Definition | Examples |
|----------|-----------|---------|
| **CRITICAL** | Deprecated API already removed in the version we target, causing runtime failure. | Python 3.14 removed module still imported, React 19 removed API still called, Pydantic V1 syntax on V2 |
| **HIGH** | Deprecated API scheduled for removal in the next major version of a dependency we use. Will break on upgrade. | `datetime.utcnow()`, SQLAlchemy 1.x `Query` API, MUI deprecated component props |
| **MEDIUM** | Deprecated API with a supported replacement available. Works today but emits warnings or will break eventually. | Legacy React lifecycle methods, deprecated Node.js APIs, old Vite config keys |
| **LOW** | Soft deprecation, style-level concern, or internal pattern the project has moved away from but remnants remain. | Old naming conventions, superseded utility functions, stale type patterns |

## Audit Dimensions

### Dimension 1: Python Standard Library & Language

**Key locations**: All `.py` files under `auralis/`, `auralis-web/backend/`, `tests/`

**Check**:
- [ ] `datetime.utcnow()` / `datetime.utcfromtimestamp()` — deprecated since 3.12, use `datetime.now(timezone.utc)` instead
- [ ] `asyncio.get_event_loop()` without running loop — deprecated, use `asyncio.get_running_loop()` or `asyncio.Runner`
- [ ] `typing` module legacy imports — `Optional[X]` vs `X | None`, `List`/`Dict`/`Tuple` vs `list`/`dict`/`tuple` (PEP 585/604)
- [ ] `pkg_resources` — deprecated in favor of `importlib.resources` / `importlib.metadata`
- [ ] `distutils` — removed in Python 3.12+
- [ ] `os.path` patterns where `pathlib.Path` is preferred and the codebase already uses `pathlib` elsewhere
- [ ] `unittest` legacy assertions (`assertEquals`, `assertNotEquals`) — deprecated aliases
- [ ] `configparser` legacy methods (`readfp`, `has_key`)
- [ ] `collections` ABCs imported from `collections` instead of `collections.abc`
- [ ] `imp` module — removed in 3.12, use `importlib`
- [ ] Thread/process `daemon` property set after `start()` — deprecated
- [ ] `ssl` deprecated functions/constants (e.g., `ssl.PROTOCOL_TLS`)
- [ ] `locale.getdefaultlocale()` — deprecated since 3.11
- [ ] f-string or `.format()` consistency where one pattern is preferred project-wide

### Dimension 2: NumPy / SciPy / Audio Libraries

**Key locations**: `auralis/core/`, `auralis/dsp/`, `auralis/analysis/`, `auralis/io/`

**Check**:
- [ ] `np.bool`, `np.int`, `np.float`, `np.complex`, `np.object`, `np.str` — removed in NumPy 1.24+, use Python builtins
- [ ] `np.product` → `np.prod`, `np.cumproduct` → `np.cumprod`, `np.sometrue` → `np.any`, `np.alltrue` → `np.all`
- [ ] `np.in1d` → `np.isin`
- [ ] `np.row_stack` → `np.vstack`
- [ ] `np.AxisError` imported from wrong location
- [ ] `scipy.fft` vs `scipy.fftpack` — `fftpack` is legacy
- [ ] `scipy.signal` deprecated function signatures (e.g., old `windows` parameter names)
- [ ] `librosa` deprecated parameters or function names (if used)
- [ ] `soundfile` deprecated APIs
- [ ] Deprecated NumPy dtype strings or casting behavior

### Dimension 3: FastAPI / Pydantic / SQLAlchemy

**Key locations**: `auralis-web/backend/`

**Check**:
- [ ] **Pydantic V1 vs V2** — `class Config:` → `model_config = ConfigDict(...)`, `.dict()` → `.model_dump()`, `.json()` → `.model_dump_json()`, `validator` → `field_validator`, `root_validator` → `model_validator`
- [ ] `from pydantic import validator` — deprecated, use `field_validator` with `mode='before'`/`'after'`
- [ ] `schema_extra` → `json_schema_extra`
- [ ] `orm_mode = True` → `from_attributes = True`
- [ ] `@app.on_event("startup")` / `@app.on_event("shutdown")` — deprecated in FastAPI, use lifespan context manager
- [ ] `Response.media_type` deprecated patterns
- [ ] **SQLAlchemy 1.x patterns** — `session.query(Model)` → `select(Model)` + `session.execute()`, `Query.filter()` → `select().where()`
- [ ] `declarative_base()` → `DeclarativeBase` class (SQLAlchemy 2.0)
- [ ] `engine.execute()` — removed in SQLAlchemy 2.0
- [ ] `Column()` → `mapped_column()` with `Mapped[]` type annotations
- [ ] `relationship()` without `Mapped[]` annotation
- [ ] `sessionmaker` deprecated `bind` parameter pattern
- [ ] `autocommit` mode — deprecated in SQLAlchemy 2.0

### Dimension 4: React / Redux / Frontend Libraries

**Key locations**: `auralis-web/frontend/src/`

**Check**:
- [ ] `ReactDOM.render()` — removed in React 18, use `createRoot()`
- [ ] `componentWillMount`, `componentWillReceiveProps`, `componentWillUpdate` — deprecated since React 16.3
- [ ] `findDOMNode` — deprecated, use refs
- [ ] `defaultProps` on function components — deprecated in React 18.3+
- [ ] `React.FC` / `React.FunctionComponent` — discouraged pattern (implicit children prop removed in React 18)
- [ ] String refs (`ref="myRef"`) — deprecated, use `useRef` / `createRef`
- [ ] `UNSAFE_` lifecycle methods still present
- [ ] Legacy context API (`contextTypes`, `childContextTypes`) — use `createContext`
- [ ] `react-redux` deprecated APIs — `connect()` HOC where hooks (`useSelector`, `useDispatch`) are available
- [ ] `createStore` → `configureStore` (Redux Toolkit)
- [ ] **MUI deprecated props/components** — `makeStyles` (JSS) vs `sx` prop / `styled`, deprecated component props per MUI version
- [ ] `@mui/styles` — deprecated in MUI v5, replaced by `@mui/system` or `styled-components`/`emotion`
- [ ] Deprecated Vite config options (e.g., `optimizeDeps.include` syntax changes)
- [ ] Deprecated `tsconfig.json` options (e.g., `moduleResolution: "node"` vs `"bundler"`)
- [ ] `PropTypes` — deprecated when TypeScript is used project-wide

### Dimension 5: Node.js / npm / Build Tools

**Key locations**: `auralis-web/frontend/package.json`, `desktop/package.json`, build configs

**Check**:
- [ ] Deprecated npm packages — check for packages marked deprecated on npm registry
- [ ] `node:` protocol — are Node.js built-ins imported with the `node:` prefix where applicable?
- [ ] Deprecated Node.js APIs (`fs.exists`, `url.parse` → `new URL()`, `querystring` → `URLSearchParams`)
- [ ] `package.json` deprecated fields (`main` without `exports`, `engines` mismatches)
- [ ] Deprecated ESLint config format (`.eslintrc.*` → `eslint.config.js` flat config)
- [ ] Deprecated testing library APIs (`cleanup` auto-behavior, `waitFor` patterns)
- [ ] Deprecated Vitest configuration options
- [ ] Electron deprecated APIs (if using older Electron patterns in `desktop/`)

### Dimension 6: Rust / PyO3 / Cargo

**Key locations**: `vendor/auralis-dsp/`

**Check**:
- [ ] Deprecated Rust standard library APIs (check edition 2021 → 2024 migration)
- [ ] PyO3 deprecated macros or API patterns (`#[pyfunction]`, `#[pymethods]` signature changes)
- [ ] Deprecated `Cargo.toml` keys or dependency specification syntax
- [ ] Deprecated crate features or APIs in dependencies
- [ ] `maturin` deprecated configuration options

### Dimension 7: Internal Codebase Deprecations

**Key locations**: Entire codebase

**Check**:
- [ ] `@deprecated` decorators or `# deprecated` comments — are callers still using deprecated internal APIs?
- [ ] `DeprecationWarning` emissions — is the codebase raising warnings that indicate migration is incomplete?
- [ ] TODO/FIXME comments referencing deprecation or migration
- [ ] Duplicate utility functions where an older version should have been removed
- [ ] Old configuration keys still accepted for backwards compatibility that should be sunset
- [ ] Stale version pins in `requirements.txt` / `package.json` that block upgrades
- [ ] Dead code that only exists for backwards compatibility with removed features

### Dimension 8: Configuration & CI/CD

**Key locations**: `pyproject.toml`, `pytest.ini`, `.github/`, `Makefile`, `*.cfg`

**Check**:
- [ ] `setup.cfg` / `setup.py` — should these be consolidated into `pyproject.toml`?
- [ ] `pytest.ini` deprecated options or marker syntax
- [ ] GitHub Actions deprecated action versions (`actions/checkout@v2` → `@v4`, `actions/setup-python@v3` → `@v5`)
- [ ] Deprecated Docker base images (if applicable)
- [ ] `mypy` deprecated configuration options
- [ ] `black` / `ruff` deprecated configuration options or rules
- [ ] Deprecated pip features or install flags

## Methodology

For each finding:
1. **Identify** the deprecated API/pattern and the file(s) using it
2. **Verify** it is actually deprecated — check official docs, changelogs, or deprecation warnings
3. **Determine** the replacement — what is the modern equivalent?
4. **Assess scope** — how many files/call sites are affected?
5. **Evaluate risk** — is this blocking an upgrade? Emitting warnings? Will it break?

## Deduplication (MANDATORY)

Before reporting ANY finding:

1. Run: `gh issue list --limit 200 --json number,title,state,labels`
2. Search for keywords from your finding in existing issue titles
3. If a matching issue exists:
   - **OPEN**: Note as "Existing: #NNN" and skip
   - **CLOSED**: Verify fix is in place. If regressed, report as "Regression of #NNN"
4. If no match: Report as NEW

## Phase 1: Audit

Write your report to: **`docs/audits/AUDIT_DEPRECATION_<TODAY>.md`** (use today's date, format YYYY-MM-DD).

### Report Structure

1. **Executive Summary** — Total findings by severity, key upgrade blockers, recommended migration order
2. **Findings** — Grouped by severity (CRITICAL first), using the per-finding format below
3. **Dependency Upgrade Roadmap** — Which packages need upgrading, in what order, and what breaks
4. **Migration Effort Estimate** — Small (< 10 call sites), Medium (10-50), Large (50+) per finding

### Per-Finding Format

```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **Dimension**: Python Stdlib | NumPy/SciPy | FastAPI/Pydantic/SQLAlchemy | React/Redux/MUI | Node/npm/Build | Rust/PyO3 | Internal | Config/CI
- **Location**: `<file-path>:<line-range>` (+ count of affected files if widespread)
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Deprecated API**: Exact function/class/method/pattern that is deprecated
- **Deprecated Since**: Version where deprecation was introduced
- **Removal Version**: Version where it will be / was removed (if known)
- **Replacement**: The modern equivalent API/pattern
- **Affected Files**: Count and list of files using the deprecated pattern
- **Evidence**: Code snippet showing current usage
- **Migration Path**: Step-by-step instructions to migrate
- **Risk**: What breaks if we don't migrate, and when
```

## Phase 2: Publish to GitHub

After completing the audit report, for every finding with **Status: NEW** or **Regression**:

1. **Create a GitHub issue** with:
   - **Title**: `[<TODAY>] <SEVERITY> - <Short Title>`
   - **Labels**: severity label (`critical`, `high`, `medium`, `low`) + `deprecation` + layer label(s) (`backend`, `frontend`, `audio-engine`, `rust-dsp`, `config`) + `maintenance`
   - **Body**:
     ```
     ## Summary
     <description>

     ## Deprecated API
     - **What**: `<deprecated function/pattern>`
     - **Deprecated since**: <version>
     - **Removed in**: <version or "TBD">
     - **Replacement**: `<modern equivalent>`

     ## Affected Files
     - `<path>:<line>` — <usage description>
     - ... (N total files)

     ## Migration Path
     1. <step>
     2. <step>

     ## Risk
     - **If not migrated**: <what breaks and when>

     ## Related Issues
     - #NNN — <relationship>

     ## Acceptance Criteria
     - [ ] All usages of `<deprecated API>` replaced with `<replacement>`
     - [ ] No deprecation warnings emitted
     - [ ] Tests pass

     ## Test Plan
     - <test description> — assert <expected>
     ```

2. **Cross-reference**: For each new issue that relates to an existing issue:
   ```
   gh issue comment <EXISTING_ISSUE> --body "Related: #<NEW_ISSUE> — <brief description>"
   ```

3. **Print a summary table** at the end:
   ```
   | Finding | Severity | Dimension | Affected Files | Action | Issue |
   |---------|----------|-----------|----------------|--------|-------|
   | <title> | HIGH | FastAPI/Pydantic | 12 | CREATED | #NNN |
   | <title> | MEDIUM | React/Redux | 5 | DUPLICATE of #NNN | — |
   ```
