# Rust DSP dependency upgrade plan

Tracked plan for the `vendor/auralis-dsp` crate's major-version bumps (#4360).
The `cargo audit` CI gate (`.github/workflows/rust-audit.yml`) covers the
*security* side; this file tracks the *currency* side.

## Current pins (`Cargo.toml`)

| Crate     | Pinned  | Latest major available | Status |
|-----------|---------|------------------------|--------|
| `pyo3`    | `0.23`  | 0.29                   | unblocked, bump tracked in #5485 |
| `numpy`   | `0.23`  | 0.29                   | unblocked, locked to pyo3 |
| `ndarray` | `0.16`  | 0.16                   | ✅ current (bumped from 0.15) |

`pyo3` and `numpy` (the `rust-numpy` crate) are version-locked to each other and
must be bumped together; `ndarray` was already advanced to 0.16 independently.

## Status: UNBLOCKED, bump pending (#5485)

### The blocker, and its re-test

On 2026-07-16 the bump to `pyo3`/`numpy` 0.29 compiled but hit a
**`rust-numpy` / NumPy ABI runtime bug**. Every array-accepting call raised
`TypeError: 'ndarray' object is not an instance of 'ndarray'` against NumPy
2.3.5, on both Python 3.13 and 3.14.

**Re-tested 2026-09-15 (#5442) against NumPy 2.4.6**, the version every manifest
now pins (`requirements.txt`, `auralis-web/backend/requirements.txt`,
`requirements-lock.txt`), on CPython 3.14.0 with Rust 1.96.0. The error **no
longer reproduces**:

- A 0.29 build (with no forward-compat flag) passes all 11 array-accepting entry
  points: `hpss`, `yin`, `chroma_cqt`, `detect_tempo`, `envelope_follow`,
  `compress`, `limit`, `compute_fingerprint`, `apply_multiband_eq`,
  `detect_onsets` and `process_chunks`.
- Its outputs are bit-identical to the shipped 0.23 build on the same inputs:
  50 output arrays and scalars compared, none differ.
- It needs two mechanical code changes. `Python::allow_threads` becomes
  `Python::detach` (12 sites in `src/py_bindings.rs`), and three `PyObject`
  return types become `Py<PyDict>`.

The Python 3.14 migration no longer depends on this bump. It finished
2026-07-28 by building 0.23 with `PYO3_USE_ABI3_FORWARD_COMPATIBILITY` (see
`.cargo/config.toml`). The bump is still worth doing: it clears both advisories
below, drops that flag and its limited-API build, and removes the hard failure
on free-threaded 3.14t (#4962). The full checklist is in #5485.

### Known advisories against the current pins (from `cargo audit`, 2026-07-19)

| Advisory | Crate | Fixed in | Reachable here? |
|----------|-------|----------|-----------------|
| [RUSTSEC-2025-0020](https://rustsec.org/advisories/RUSTSEC-2025-0020) — buffer overflow in `PyString::from_object` | pyo3 0.23.5 | >= 0.24.1 | **No** — we never call `PyString::from_object` |
| [RUSTSEC-2026-0177](https://rustsec.org/advisories/RUSTSEC-2026-0177) — missing `Sync` bound on `PyCFunction::new_closure` | pyo3 0.23.5 | >= 0.29.0 | **No** — we never call `PyCFunction::new_closure` |

Our crate uses only `pyo3::prelude`, `PyModule`, and `PyDict`, so neither
vulnerable API is on our call surface — the practical exposure is nil. Both are
therefore `--ignore`'d in the `cargo audit` CI step (see the workflow) so the
gate stays green for *new* advisories rather than being permanently red on two
unreachable ones. **These ignores must be removed the moment the pyo3 bump
lands** (#5485). RUSTSEC-2026-0177's fix requires pyo3 0.29, the version the
re-test above cleared.

## Re-evaluation trigger

Revisit when **any** of these becomes true:

1. The `cargo audit` gate flags an advisory against a pinned crate → bump becomes
   urgent; pin forward to the patched version even if a major jump is required.
2. ~~`rust-numpy` ships a release confirmed compatible with our NumPy on
   3.13/3.14 (clears the ABI blocker).~~ **Met 2026-09-15** (#5442): 0.29 works
   against NumPy 2.4.6.
3. ~~The Python 3.14 migration lands.~~ Landed 2026-07-28 without the bump (see
   above).

With trigger 2 met, the remaining work is the bump itself (#5485), not another
re-evaluation.
