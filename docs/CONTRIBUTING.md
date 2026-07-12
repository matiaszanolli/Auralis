# Contributing to Auralis

This is the developer on-ramp: get the project running, understand the ground rules, and know
how to test and ship a change. For architecture, start at
[architecture/overview.md](architecture/overview.md).

---

## 1. Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| **Python** | 3.14+ | The requirement; the test env still runs 3.13.9 transitionally |
| **Node** | 24+ | Frontend + Electron |
| **Rust** | stable + `maturin` | Required — the DSP module has no Python fallback |

---

## 2. First-time setup

```bash
# 1. Python deps
pip install -r requirements.txt

# 2. Build the Rust DSP module (REQUIRED before first run)
cd vendor/auralis-dsp && maturin develop && cd ../..

# 3. Frontend deps
cd auralis-web/frontend && npm install && cd ../..

# 4. Run everything (backend :8765, frontend :3000)
python launch-auralis-web.py --dev
```

Run components individually when iterating:

```bash
cd auralis-web/backend && python -m uvicorn main:app --reload   # backend only
cd auralis-web/frontend && npm run dev                          # frontend only
cd desktop && npm install && npm run dev                        # Electron shell
```

> If startup raises `RuntimeError: ... auralis_dsp`, you skipped step 2. The Rust module is not
> optional — see [subsystems/dsp-engine.md §5](subsystems/dsp-engine.md#5-rust-dsp-module-vendorauralis-dsp).

More detail: [development/DEVELOPMENT_SETUP_BACKEND.md](development/DEVELOPMENT_SETUP_BACKEND.md)
· [development/DEVELOPMENT_SETUP_FRONTEND.md](development/DEVELOPMENT_SETUP_FRONTEND.md).

---

## 3. Ground rules (the ones that cause bugs when ignored)

These are distilled from [`CLAUDE.md`](../CLAUDE.md) and
[development/DEVELOPMENT_STANDARDS.md](development/DEVELOPMENT_STANDARDS.md). Read those for the
full list.

### Audio DSP

```python
assert len(output) == len(input)      # never change sample count — gapless playback depends on it
assert isinstance(output, np.ndarray) # always NumPy, never lists
output = audio.copy()                 # never modify in place
```

- Load metadata (sample rate, channels) **before** processing.
- Vectorize with NumPy over chunks, not per-sample loops.
- No NaN/Inf may escape — guard with `validate_audio_finite` / `sanitize_audio`.

### Python backend

- Routers are auto-included via `include_router()`; all handlers are `async def`.
- Errors go through `HTTPException`, never bare exceptions.
- Shared state is protected with the right primitive — `asyncio.Lock` (event-loop state),
  `threading.RLock` (CPU/thread-pool state), `contextvars` (per-stream isolation).
- **All DB access via repositories** ([`auralis/library/repositories/`](../auralis/library/repositories/))
  — never raw SQL. Avoid N+1 with `selectinload()`.

### React frontend

- **`@/` absolute imports only** — no `../../../`.
- Colors and spacing come from `import { tokens } from '@/design-system'` — no hardcoded
  hex/rgb.
- Components target **< 300 lines** (split into subcomponents + `.styles.ts`).
- **Redux is the single source of truth** for playback/queue — don't add WS-shadow state.
- Frontend WS/API types must match backend `schemas.py`.

### Project principles

1. **DRY** — improve existing code, never duplicate. Reach for shared utilities.
2. **Modular** — < 300 lines per module, single responsibility.
3. **No variants** — no `Enhanced`/`V2`/`Advanced` copies. Refactor in place.
4. **Repository pattern** for all DB access.

---

## 4. Testing

Full guidance: [development/TESTING_GUIDELINES.md](development/TESTING_GUIDELINES.md) (mandatory
reading) and [development/TEST_EXECUTION_GUIDE.md](development/TEST_EXECUTION_GUIDE.md).

```bash
# Python
python -m pytest tests/ -v                        # all (~2–3 min)
python -m pytest -m "not slow" -v                  # fast subset (PR gate)
python -m pytest tests/path.py::test_name -vv -s   # single test

# Frontend (needs 2 GB heap — the full suite OOMs otherwise)
cd auralis-web/frontend && npm run test:memory

# Type checks
mypy auralis/ auralis-web/backend/ --ignore-missing-imports
cd auralis-web/frontend && npm run type-check
```

**Known-flaky / non-green suites** (don't be alarmed, and don't gate on them):

- The full `tests/backend` suite never goes fully green (broken v15→v16 migration cascades) —
  gate on **targeted domain tests**, not the whole suite.
- `tests/backend/test_system_api.py` and `tests/concurrency/test_thread_safety.py` **hang** when
  run as whole files — run scoped classes/tests.
- The frontend suite has a set of pre-existing failures; compare against a clean baseline using
  a `git worktree` (see the git note below) rather than assuming your change caused them.

Generate tests with the `gen-test` skill; verify a change actually works end to end with the
`verify` skill.

---

## 5. Git & PR workflow

- Branch from `master`. Prefixes: `feature/`, `fix/`, `refactor/`, `docs/`.
- Commit format: `type: description` (e.g. `fix: clamp currentTime to duration`).
- **Before opening a PR:** `pytest -m "not slow" -v` + both type checks pass.
- `Closes #NNNN` in a pushed commit auto-closes the issue.
- Commits to `master` do **not** auto-push — push manually.

> ⚠️ **Never use `git stash` in this repo** — there is a pre-existing `baseline-check` stash
> hazard. To run against a clean or prior state, use `git worktree add <path> HEAD` instead, or
> `git show HEAD:path > path`.

---

## 6. Where to look for structure

- **Codebase graph queries** ("who calls this", "what's the architecture") — the
  `codebase-memory` skill.
- **Trace a user action across layers** — the `trace-flow` skill.
- **Audit a subsystem** — the `audit-*` skills (backend, frontend, engine, security,
  concurrency, …).

---

## 7. Documentation

When your change alters behavior a developer relies on, update the matching doc:

- Architecture/flow change → [architecture/](architecture/)
- Subsystem behavior → [subsystems/](subsystems/)
- New convention or gotcha → this file or the relevant subsystem doc

Keep the [docs hub](README.md) links working. Historical write-ups belong in
[archive/](archive/), not alongside the living docs.
