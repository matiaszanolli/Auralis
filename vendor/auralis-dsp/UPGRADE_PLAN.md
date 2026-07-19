# Rust DSP dependency upgrade plan

Tracked plan for the `vendor/auralis-dsp` crate's major-version bumps (#4360).
The `cargo audit` CI gate (`.github/workflows/rust-audit.yml`) covers the
*security* side; this file tracks the *currency* side.

## Current pins (`Cargo.toml`)

| Crate     | Pinned  | Latest major available | Status |
|-----------|---------|------------------------|--------|
| `pyo3`    | `0.23`  | 0.25 / 0.26            | held — see below |
| `numpy`   | `0.23`  | 0.25 / 0.26            | held — locked to pyo3 |
| `ndarray` | `0.16`  | 0.16                   | ✅ current (bumped from 0.15) |

`pyo3` and `numpy` (the `rust-numpy` crate) are version-locked to each other and
must be bumped together; `ndarray` was already advanced to 0.16 independently.

## Status: DEFERRED — blocked (with 2 known, non-reachable advisories)

The bump is **not** a mechanical version change. Bumping `pyo3` to 0.25+/`numpy`
to the matching release compiles, but hits a **`rust-numpy` / NumPy ABI runtime
bug** against the NumPy 2.3.x we run on, on both Python 3.13 and 3.14. `pyo3`
0.23 also caps the supported CPython at 3.13, which is entangled with the wider
Python 3.14 migration (still transitional).

### Known advisories against the current pins (from `cargo audit`, 2026-07-19)

| Advisory | Crate | Fixed in | Reachable here? |
|----------|-------|----------|-----------------|
| [RUSTSEC-2025-0020](https://rustsec.org/advisories/RUSTSEC-2025-0020) — buffer overflow in `PyString::from_object` | pyo3 0.23.5 | >= 0.24.1 | **No** — we never call `PyString::from_object` |
| [RUSTSEC-2026-0177](https://rustsec.org/advisories/RUSTSEC-2026-0177) — missing `Sync` bound on `PyCFunction::new_closure` | pyo3 0.23.5 | >= 0.29.0 | **No** — we never call `PyCFunction::new_closure` |

Our crate uses only `pyo3::prelude`, `PyModule`, and `PyDict`, so neither
vulnerable API is on our call surface — the practical exposure is nil. Both are
therefore `--ignore`'d in the `cargo audit` CI step (see the workflow) so the
gate stays green for *new* advisories rather than being permanently red on two
unreachable, currently-unfixable ones. **These ignores must be removed the moment
the pyo3 bump lands** (RUSTSEC-2026-0177's fix in particular *requires* pyo3
0.29, the exact version blocked by the ABI bug above — so clearing it and
clearing the ABI blocker are the same task).

## Re-evaluation trigger

Revisit when **any** of these becomes true:

1. The `cargo audit` gate flags an advisory against a pinned crate → bump becomes
   urgent; pin forward to the patched version even if a major jump is required.
2. `rust-numpy` ships a release confirmed compatible with our NumPy on 3.13/3.14
   (clears the ABI blocker).
3. The Python 3.14 migration lands, at which point `pyo3` must move off 0.23
   regardless.

Until then the CI advisory scan is the safety net; this doc is the reminder that
the majors are intentionally held back, not forgotten.
