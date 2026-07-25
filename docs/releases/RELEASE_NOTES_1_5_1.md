# Auralis v1.5.1 — Recovery Milestone

**Status:** Unreleased; not ready to tag or publish

**Prepared:** 2026-07-24

**Purpose:** Establish a truthful, testable starting point for restoring a working application

## Summary

v1.5.1 begins the working-state recovery. It does not claim the application is finished—or
even working end to end yet. The repository has usable foundations: the FastAPI backend boots
and serves real API requests, the React frontend creates a production bundle, and several
high-risk regression slices pass. The supported launcher and four product-critical flows still
block a release.

The complete evidence and implementation order are in the
[working-state recovery audit](../audits/AUDIT_RECOVERY_2026-07-24.md).

## Included in this preparation

- Product, compatibility, backend, Python packaging, container, root package, frontend, and
  desktop metadata aligned on `1.5.1`.
- Backend version reporting moved back to the canonical `auralis/version.py` product version.
- Version synchronization expanded to cover every derived release surface.
- A dependency-free CI preflight and regression tests added to prevent version drift.
- README and maintained documentation rewritten around the actual recovery state.
- A release checklist tied to the audit’s definition of “working.”
- Release packaging hardened for Linux x64 AppImage, Flatpak, and `.deb`, Windows x64, and
  macOS Apple Silicon. Missing or wrong-architecture artifacts now fail the build.
- The desktop renderer now uses one runtime semantic theme across MUI, Emotion, and native DOM
  controls. The shell, navigation, library, inspection pane, player, queue, and dialogs share
  a consistent surface hierarchy in dark and light modes.
- Standalone browser/PWA use is deprecated. Browser execution remains available as an
  unsupported renderer-development preview; Electron is the only official application
  platform.
- The production TypeScript gate is green after making the cache-health timestamp fallback
  match the backend's actual optional response field.

No launcher, fingerprint, mono-processing, or rapid-selection product fix is included yet.

## Release blockers

1. **REC-01 — launcher ownership and readiness:** the root launcher resolves incorrect paths;
   after a path-only fix, root and Electron would race to own the backend. Cleanup can kill an
   unrelated process on port 8765.
2. **REC-02 — fresh fingerprint persistence:** fresh schemas provide no server default for
   `is_reference`; raw inserts omit it and silently fail.
3. **REC-03 — two-dimensional mono input:** `(samples, 1)` reaches loudness code that indexes
   a nonexistent second channel.
4. **REC-04 / #4426 — last intent loses:** two rapid track requests can leave the older track
   active.

The release must also replace optimistic liveness with real readiness and turn the existing
full-stack script into a collected, isolated smoke test.

## What is already verified

- Core Python and backend modules import in the audited environment.
- A real isolated backend reached `/api/health` in about two seconds.
- Frontend production build: pass.
- Release metadata/system endpoint slice: 12/12 pass.
- Python↔Rust fingerprint boundary: 8/8 pass.
- Targeted WebSocket, pagination, and play tests: 43/43 pass.
- Targeted July high-risk Python regressions: 77 pass, 4 skipped.

These results establish a recovery base; they do not supersede the open release blockers.
The production TypeScript gate now passes. The interface migration deliberately leaves
lower-traffic component-level color debt for follow-up; the current migration boundary is
documented in the UI theme audit linked from the changelog.

See the [desktop UI theme audit](../audits/UI_THEME_UNIFICATION_2026-07-25.md) for the exact
migration boundary, platform policy, and ordered follow-up debt.

## Compatibility

- Product version: `1.5.1`
- Database schema: `16` (unchanged)
- Fingerprint algorithm: `3` (unchanged)
- Required toolchain target: Python 3.14+, Node 24+, pnpm 10, Rust stable
- Last tagged source release: `v1.2.1-beta.1`
- Last documented binary release: `v1.2.0-beta.2`

No schema or fingerprint reprocessing migration is expected from this metadata-only bump.

## Installation and artifacts

There are no v1.5.1 artifacts. During recovery, use the separate backend and Vite component
workflow in the [README](../../README.md#option-2-run-the-verified-components-from-source).
Do not tag v1.5.1: the tag triggers cross-platform builds and creates a draft GitHub release.
The macOS target is Apple Silicon only; signing and notarization credentials are not yet
configured, so any CI-produced DMG must be treated as an unsigned test artifact until that
release gate is completed.

## Exit criteria

The release can be tagged only after every item in
[RELEASE_CHECKLIST_1_5_1.md](RELEASE_CHECKLIST_1_5_1.md) is complete, including the audit’s
eleven-point [definition of “working”](../audits/AUDIT_RECOVERY_2026-07-24.md#definition-of-working)
against a fresh, isolated home and database.
