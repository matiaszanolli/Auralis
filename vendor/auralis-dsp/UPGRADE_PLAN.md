# Rust DSP dependency upgrade plan

Tracked plan for the `vendor/auralis-dsp` crate's major-version bumps (#4360).
The `cargo audit` CI gate (`.github/workflows/rust-audit.yml`) covers the
*security* side; this file tracks the *currency* side.

## Current pins (`Cargo.toml`)

| Crate     | Pinned  | Latest major available | Status |
|-----------|---------|------------------------|--------|
| `pyo3`    | `0.29`  | 0.29                   | ✅ current (bumped from 0.23, #5485) |
| `numpy`   | `0.29`  | 0.29                   | ✅ current (bumped with pyo3, #5485) |
| `ndarray` | `0.16`  | 0.16                   | ✅ current (bumped from 0.15) |

`pyo3` and `numpy` (the `rust-numpy` crate) are version-locked to each other and
must be bumped together; `ndarray` was advanced to 0.16 independently and is
still the single `ndarray` in the graph (`cargo tree -d`).

## Status: CURRENT (#5485)

### History of the 0.23 → 0.29 bump

On 2026-07-16 the bump to `pyo3`/`numpy` 0.29 compiled but hit a
**`rust-numpy` / NumPy ABI runtime bug**. Every array-accepting call raised
`TypeError: 'ndarray' object is not an instance of 'ndarray'` against NumPy
2.3.5, on both Python 3.13 and 3.14. The crate stayed on 0.23 and reached
Python 3.14 (2026-07-28) by building with `PYO3_USE_ABI3_FORWARD_COMPATIBILITY`,
which silently compiled pyo3-ffi against the limited C API (#4911) and ruled out
free-threaded 3.14t (#4962).

Re-tested 2026-09-15 (#5442) against NumPy 2.4.6, the version every manifest
pins, the error no longer reproduced. The bump landed on 2026-09-17 (#5485):

- `pyo3` 0.23.5 → 0.29.2, `numpy` 0.23.0 → 0.29.0. Their `rust-version` is
  1.83, below the crate's edition-2024 floor of 1.85, so `rust-version` is
  unchanged.
- `Python::allow_threads` → `Python::detach` (11 call sites in
  `src/py_bindings.rs`), and the three `PyObject` returns (`compress`, `limit`,
  `compute_fingerprint`) became `Py<PyDict>`.
- `.cargo/config.toml` and its `PYO3_USE_ABI3_FORWARD_COMPATIBILITY` env block
  were deleted. `Cargo.toml` requests no `abi3` feature, so the release wheel is
  now a full-API `cp314-cp314` build. `build-release.yml` asserts that shape.
- Verified on CPython 3.14.0, NumPy 2.4.6, Rust 1.96.0: all 11 array-accepting
  entry points (`hpss`, `yin`, `chroma_cqt`, `detect_tempo`, `envelope_follow`,
  `compress`, `limit`, `compute_fingerprint`, `apply_multiband_eq`,
  `detect_onsets`, `process_chunks`) return outputs bit-identical to the 0.23
  build on the same deterministic inputs.
- One user-visible difference: an array of the wrong dtype (for example float32
  passed to `hpss`) still raises `TypeError`, but 0.29 words it as
  `'ndarray' object is not an instance of 'ndarray'` instead of
  `argument 'audio': 'ndarray' object cannot be converted to 'PyArray<T, D>'`.
  That is the same text as the July "ABI" error, so if it appears, check the
  caller's dtype first. No code depends on the message.

### Advisories

`cargo audit` is clean with no `--ignore` flags. The two pyo3 0.23 advisories
the gate used to ignore are fixed by the bump:

| Advisory | Crate | Fixed in |
|----------|-------|----------|
| [RUSTSEC-2025-0020](https://rustsec.org/advisories/RUSTSEC-2025-0020) — buffer overflow in `PyString::from_object` | pyo3 0.23.5 | >= 0.24.1 |
| [RUSTSEC-2026-0177](https://rustsec.org/advisories/RUSTSEC-2026-0177) — missing `Sync` bound on `PyCFunction::new_closure` | pyo3 0.23.5 | >= 0.29.0 |

Neither API was ever on this crate's call surface.

### Free-threaded CPython (3.14t)

pyo3 0.29 no longer hard-fails the build on a free-threaded interpreter (#4962).
Since pyo3 0.28, free-threaded support is opt-out: `#[pymodule]` without
`gil_used = true` declares the module safe to import without the GIL, and this
crate relies on that default. That is plausible here, because the crate has no
`static`, interior-mutability or `unsafe` state, and every wrapper copies its
input array before `detach`. It is still untested. No CI job builds or runs
3.14t, and the rest of the Python stack (numba, for example) has not been
checked on it. The project therefore still supports only the GIL-enabled build
(`docs/CONTRIBUTING.md`).

## Re-evaluation trigger

Revisit when **any** of these becomes true:

1. The `cargo audit` gate flags an advisory against a pinned crate → bump becomes
   urgent; pin forward to the patched version even if a major jump is required.
2. A new `pyo3`/`numpy` minor ships (0.x minors are breaking). Bump both
   together, rebuild with `maturin develop`, and re-run the Rust validation
   tests (`tests/test_*_rust_validation.py`,
   `tests/test_pyo3_channel_axis_guards_4502.py`,
   `tests/vendor/test_rust_panic_handler.py`).
3. Bumping `ndarray` to 0.17. `numpy` 0.29 accepts `>=0.15, <=0.17`, so the two
   stay unified, but re-check `cargo tree -d` so the graph never ends up with two
   `ndarray` versions.
