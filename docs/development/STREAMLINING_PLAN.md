# Streamlining Plan

Enforces the "No variants" principle ([CLAUDE.md](../../CLAUDE.md), Principles #3) by
retiring parallel implementations of the same concept, one at a time. Every candidate found
so far is either retired or classified as intentional; this page records the intentional ones
so an audit does not re-file them, and the playbook for the next candidate.

The main risk is collapsing variation that is deliberate. Read
[Intentional variation](#intentional-variation-do-not-collapse) before merging anything that
looks like a duplicate.

## Open candidates

None. List a new alternate here, with the grep that shows its call sites and its survivor.

## Playbook

One PR per item, independently revertible.

1. Re-grep the call sites. Grep the class name, its aliases, and any factory function that
   returns it; do not let a path filter on the source tree also exclude the mirrored `tests/`
   tree.
2. Pick the survivor: the default, better-tested, more-referenced implementation.
3. Migrate call sites to the survivor.
4. Delete the alternate in the same PR. No deprecation shims; the repo refactors in place.
5. Drive the affected path (run the app or the CLI), not only the tests.
6. Update the subsystem doc under `docs/subsystems/` if documented behaviour changed.
7. Update `loc-ceilings.json` and the baselines if a listed file shrank or a baselined test went
   away (see [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md)).

## Intentional variation (do not collapse)

- **Offline mastering subsystem vs the shipped path.** `auralis/core/simple_mastering.py`
  (`SimpleMasteringPipeline`), `auralis/core/stages/`, `auralis/core/mastering_branches/` and
  the `auralis/core/mastering_*.py` modules are reached only from the root `auto_master.py` CLI.
  The app's audio goes `HybridProcessor.process()` to `ContinuousMode`. Each entry module
  carries an in-module banner saying so. Unreachable from the app is not dead: the CLI is a
  working tool, and retiring the subsystem is a decision about that tool. Do not re-file it as
  dead code.
- **`RecordingTypeDetector`** (`auralis/core/recording_type_detector.py`) is reached only from
  `scripts/rate_track.py`. Same treatment: offline, kept.
- **`ContinuousMasteringBranch` vs `ContinuousMode`.** `core/mastering_branches/continuous.py`
  belongs to the offline pipeline; `core/processing/continuous_mode.py` is what the app runs.
- **`AdaptiveMode` and `HybridMode`** (`auralis/core/processing/`). The `adaptive` mode runs
  `ContinuousMode` (`core/processing/mode_dispatch.py`). `HybridMode` wraps `AdaptiveMode` and is
  reached through processing jobs in `reference` / `hybrid` mode
  (`auralis-web/backend/core/job_execution.py`, `job_lifecycle.py`), so `AdaptiveMode` stays as its
  backing.
- **`SpectrumMapper` vs `AdaptiveTargetGenerator`** (`auralis/core/analysis/`). Complementary
  parameter generators feeding different stages of `AdaptiveMode.process`; `AdaptiveMode` takes
  both in its constructor. `SpectrumMapper` retires only together with `AdaptiveMode`.
- **`FingerprintStorage` vs `SidecarManager`.** `auralis/analysis/fingerprint/fingerprint_storage.py`
  is the machine-local, content-keyed `.25d` cache under `~/.auralis/fingerprints/`;
  `auralis/library/sidecar_manager.py` writes the portable per-file sidecar next to the audio.
  Sharing the `.25d` serializer between them is the only cleanup on offer.
- **`analysis/quality/` vs `analysis/quality_assessors/`.** `quality/` builds on the base layer in
  `quality_assessors/` (`base_assessor`, `utilities/scoring_ops`); layered, not duplicated.
- **Two processor caches.** `auralis/core/hybrid_processor_singleton.py` is a small LRU in the
  core library; the backend's `ProcessorFactory`
  (`auralis-web/backend/core/processor_factory.py`) is the larger, leased cache. The core library
  cannot import the backend, so these sit at different layers.

## Do not re-add

- A realtime `AdaptiveLimiter` / `RealtimeAdaptiveEQ` / `RealtimeDSPPipeline` chain: it had no
  production caller and its block-FFT EQ applied gain with no window and no overlap-add, so it
  was never WOLA-safe.
- A Rust gRPC fingerprint server or a Python sampling-strategy fingerprint path. The Rust
  `compute_fingerprint` (PyO3) is the single fingerprint implementation; Python only adapts its
  output to the schema (`auralis/analysis/fingerprint/rust_fingerprint.py`,
  `compute_fingerprint_schema`).
- A second generic REST client in the frontend. `useRestAPI`
  (`auralis-web/frontend/src/hooks/api/useRestAPI.ts`) is the generic hook.
