# Auralis v1.5.1 — Recovery Milestone

**Status:** Unreleased; not ready to tag or publish

**Prepared:** 2026-07-24; gate status refreshed 2026-11-23

**Purpose:** Establish a truthful, testable starting point for restoring a working application

## Summary

v1.5.1 begins the working-state recovery. It does not claim the application is finished.
The FastAPI backend boots and serves real API requests, the React frontend creates a production
bundle, and the three product-flow defects found by the recovery audit (REC-02 to REC-04) are
fixed and re-verified. The source launcher (REC-01, REC-05) is implemented and covered by a
collected smoke test. What blocks a tag is validation of the installed artifacts, the audit's
end-to-end definition of “working” against a fresh home, and signing credentials.

The complete evidence and implementation order are in the
[working-state recovery audit](../audits/AUDIT_RECOVERY_2026-07-24.md). The changes since
preparation are in the [changelog](CHANGELOG.md#unreleased).

## Included in this preparation

- Product, compatibility, backend, Python packaging, root package, frontend, and
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

Since preparation, the fingerprint (#5530), mono-processing (#5550, #6118) and rapid-selection
(#4426) fixes have landed and were re-verified on 2026-11-22, and the supervised launcher
(`9315886dc`) replaced the broken root launcher. See the
[release checklist](RELEASE_CHECKLIST_1_5_1.md) for each gate's evidence.

## Release blockers

Product blockers from the audit:

1. **REC-01 — launcher ownership and readiness:** *Source launch resolved* by
   `launch-auralis-web.py` (`9315886dc`) and issues #4805, #5373, #5447, and #6157; the collected
   smoke `tests/integration/test_application_startup.py` covers one backend owner, readiness
   before success, failed initialization, port collision, and child reaping. *Open:* the packaged
   Electron launch in its default sandbox configuration and the installed artifacts.
2. **REC-02 — fresh fingerprint persistence:** *Resolved: #5530, re-verified 2026-11-22.*
3. **REC-03 — two-dimensional mono input:** *Resolved: #5550, #6118, re-verified 2026-11-22.*
4. **REC-04 / #4426 — last intent loses:** *Resolved: #4426, re-verified 2026-11-22.*
5. **REC-05 — optimistic liveness:** *Resolved for source and packaged Electron:* `/api/ready`
   reports initialized engine and database state, and both supervisors poll it with the launch ID.

Remaining release gates:

- The eleven-point definition of “working” has not been run end to end against a fresh,
  isolated home and database, and the repeated-run gates have not been run.
- No installed artifact has been smoke-tested on its target platform.
- Windows Authenticode and macOS Developer ID signing and notarization are not configured
  (#4905), and the GPG key that signs `SHA256SUMS.txt` has no published fingerprint.

## What is already verified

Evidence from the 2026-07-24 audit and the fixes that followed:

- Core Python and backend modules import in the audited environment.
- A real isolated backend reached `/api/health` in about two seconds.
- Frontend production build and production type-check: pass.
- Release metadata/system endpoint slice: 12/12 pass.
- Python↔Rust fingerprint boundary: 8/8 pass.
- Targeted WebSocket, pagination, and play tests: 43/43 pass.
- Targeted July high-risk Python regressions: 77 pass, 4 skipped.
- The pytest, nightly slow-suite, and frontend CI baselines list no known failures (#6709, #6076).
  The CI gates fail on any new failure, so a green run is meaningful for the suites CI runs.
- Fresh-schema fingerprint persistence, mono at the array and stream boundaries, and
  rapid-selection ordering each have a committed regression test; the checklist names them.

These results establish a recovery base; they do not substitute for the end-to-end run against
a fresh home that the release checklist requires. The interface migration deliberately leaves
lower-traffic component-level color debt for follow-up; the current migration boundary is
documented in the UI theme audit linked from the changelog.

See the [desktop UI theme audit](../audits/UI_THEME_UNIFICATION_2026-07-25.md) for the exact
migration boundary, platform policy, and ordered follow-up debt.

## Compatibility

- Product version: `1.5.1`
- Database schema: `34` (was `16` at the 1.5.0 source milestone)
- Fingerprint algorithm: `16` (was `4` at that milestone)
- Required toolchain target: Python 3.14+, Node 24+, pnpm 10, Rust (pinned in
  `vendor/auralis-dsp/rust-toolchain.toml`)
- Last tagged source release: `v1.2.1-beta.1`
- Last documented binary release: `v1.2.0-beta.2`

An existing library migrates on first start and keeps a pre-migration backup. The migration to
schema 31 makes the next scan re-read every track, because albums are now owned by the file's
ALBUMARTIST tag (#6332). Stored fingerprints from any earlier algorithm version are recomputed
by the background queue. The user-visible effect of the schema and algorithm changes is itemized
in the [changelog](CHANGELOG.md#unreleased).

## Installation and artifacts

There are no v1.5.1 artifacts. During recovery, run from source with the launcher described in
[FIRST_TIME_SETUP.md](../../FIRST_TIME_SETUP.md) and the [README](../../README.md).
Do not tag v1.5.1: the tag triggers cross-platform builds and creates a draft GitHub release.
The macOS target is Apple Silicon only. Signing and notarization credentials are not configured
(#4905), so any CI-produced DMG or Windows installer is an unsigned test artifact until that
release gate is completed. The workflow GPG-signs `SHA256SUMS.txt` only when the repository key is
configured; the key fingerprint is not yet published.

## Exit criteria

The release can be tagged only after every item in
[RELEASE_CHECKLIST_1_5_1.md](RELEASE_CHECKLIST_1_5_1.md) is complete, including the audit’s
eleven-point [definition of “working”](../audits/AUDIT_RECOVERY_2026-07-24.md#definition-of-working)
against a fresh, isolated home and database.
