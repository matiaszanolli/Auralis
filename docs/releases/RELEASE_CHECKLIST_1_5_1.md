# v1.5.1 Release Checklist

**State:** Prepared, blocked. Product blockers REC-02 to REC-04 and the source launcher are
verified. Open: the packaged and installed launch, the end-to-end working-state run, the
repeated-run gates, and artifact validation.

**Rule:** Do not create or push `v1.5.1` until every release gate below is checked.

## Preparation

- [x] Canonical version advanced to `1.5.1`.
- [x] Python package, compatibility module, backend fallback, root package,
  frontend, desktop, and packaging metadata aligned.
- [x] Canonical changelog updated.
- [x] Release notes written.
- [x] Working-state audit linked from the README and documentation hub.
- [x] Version consistency regression added.
- [x] Cross-platform packaging workflow requires Linux AppImage, Flatpak, and `.deb`, Windows
  x64, and macOS Apple Silicon artifacts.
- [x] Documentation path-reference audit and whitespace validation pass.
- [ ] Release commit reviewed and merged.

## Working-state blockers

The [application startup](../prd/application-startup.md) and
[library and playback recovery](../prd/library-playback-recovery.md) PRDs link the current
component evidence and define how to verify the complete workflows. Check each gate when its
release validation passes.

- [x] **REC-01, source launch:** one launcher, `launch-auralis-web.py`, owns the backend and Vite,
  installs nothing at runtime, propagates one port, and stops only its own process groups.
  *Fixed in `9315886dc` and closed issues #4805, #5373, #5447, and #6157 (Electron no longer kills
  by port). `pnpm run dev` delegates to the launcher via `dev.js`. The cases in
  `tests/integration/test_application_startup.py` cover one backend owner, a ready URL printed only
  after `/api/ready` succeeds, backend and launcher exit reaping every child, failed
  initialization, and a port collision that leaves the unrelated listener running.*
- [ ] **REC-01, packaged Electron:** the packaged app owns its backend (`desktop/main.js`: launch ID
  checked against `/api/ready`, build-time backend digest #6527, backend exits with its parent
  #6720) and shuts it down without orphans, in the default Chromium sandbox configuration, from the
  installed artifacts. No installed artifact has been exercised yet.
- [x] **REC-02:** fresh and migrated databases both persist and reload fingerprints.
  *Verified 2026-11-22 (#6678). Fixed by #5530 (`fdbeba651`). Fresh schema:
  `tests/auralis/library/test_fingerprint_fresh_install_defaults_5530.py` and
  `tests/auralis/library/test_reference_cloud_v15.py`. Migrated schema: an insert and an update
  `upsert()` each reloaded through `get_by_track_id()` on a copy of a migration-built v33
  library. No committed test covers the migrated half yet.*
- [x] **REC-03:** one-dimensional and `(samples, 1)` mono fixtures play in normal and enhanced
  modes without changing sample count or producing non-finite PCM.
  *Verified 2026-11-22 (#6678). Fixed by #5550 (`e22499901`) and #6118 (`f227aeb83`).
  Arrays: `tests/auralis/dsp/test_loudness_channel_counts_5550.py`,
  `tests/auralis/core/test_hybrid_input_contract_6118.py`,
  `tests/auralis/test_audio_processing_invariants.py`. Streams: a mono file plays whole and
  finite through `play_normal` and `play_enhanced` in
  `tests/backend/test_ws_streaming_end_to_end_6001.py`.*
- [x] **REC-04 / #4426:** two rapid selections deterministically leave the second track active.
  *Verified 2026-11-22 (#6678). Fixed in `ae18b2484`.
  `auralis-web/frontend/src/hooks/player/__tests__/usePlayTrack.test.ts` resolves the older
  request last and asserts only the second track starts.*
- [x] **REC-05:** `/api/ready` reports initialized engine and database state and the launch ID
  (`tests/backend/test_health_readiness_4684.py`); the launcher and Electron wait on it.
- [x] The collected [source startup smoke](../../tests/integration/test_application_startup.py)
  exercises real backend and Vite processes with ephemeral ports and a temporary
  home/database. It verifies initialization failure, child exit, cleanup, and port collision.

Linux source smoke passed on 2026-11-19, before the supervisor landed as `9315886dc` on
2026-11-20; re-run `tests/integration/test_application_startup.py` on the release commit. An Xvfb
Electron development run loaded the Vite window and reaped the launcher's three child processes
with a test-only Chromium sandbox override. Validate the default Electron configuration and the
installed artifacts on their target systems.

## Required validation

- [x] Version consistency:

  ```bash
  python scripts/validate_release_metadata.py --expected 1.5.1
  python -m pytest tests/regression/test_release_version_consistency.py -q
  ```

- [x] Python dependency integrity in the audited environment:

  ```bash
  uv pip check
  ```

- [x] Frontend production type-check:

  ```bash
  cd auralis-web/frontend
  pnpm install --frozen-lockfile
  pnpm run type-check:prod
  ```

- [x] Frontend production build:

  ```bash
  cd auralis-web/frontend
  pnpm run build
  ```

- [ ] Targeted Python library, mono, playback-selection, startup, and prior high-risk regression
  slices pass.
- [ ] Python↔Rust boundary tests and the Rust library gate pass (`rust-audit.yml` covers advisories
  only; run `cargo test` in `vendor/auralis-dsp` and the boundary tests locally).
- [ ] The eleven-point
  [definition of “working”](../audits/AUDIT_RECOVERY_2026-07-24.md#definition-of-working)
  passes against a fresh temporary home/database.
- [ ] The fast working-state gate passes three consecutive times.
- [ ] Ten repeated end-to-end runs complete without a wrong track, orphan process, HTTP 500,
  uncaught UI exception, or PCM invariant violation.

## Artifact validation

- [ ] `git status` is clean at the release commit.
- [ ] The release commit contains no secrets, generated local databases, logs, or cache output.
- [ ] Linux x64 AppImage, Flatpak, and `.deb` install and pass the working-state smoke.
- [ ] Windows installer installs, launches, upgrades/uninstalls, and passes the smoke.
- [ ] macOS Apple Silicon DMG launches and passes the smoke; unsigned and unnotarized
  limitations are stated until signing credentials are configured.
- [ ] Signing status is stated for each platform. Authenticode, Developer ID, and notarization
  are not configured (#4905), and `verifyUpdateCodeSignature`, `hardenedRuntime`, and
  `gatekeeperAssess` stay disabled in `desktop/package.json` until they are.
- [ ] SHA-256 checksums are generated and verified for every published artifact. The workflow
  signs `SHA256SUMS.txt` with GPG only when `RELEASE_GPG_PRIVATE_KEY` is configured; either
  publish the key fingerprint (README, Release Verification) or state that the checksums are
  unsigned.
- [ ] Version displayed by `/api/version`, Electron metadata, filenames, and release title is
  exactly `1.5.1`.
- [ ] Known limitations in the final GitHub release match the tested artifacts.

## Tag and publish

Only after all prior sections are green:

```bash
python sync_version.py 1.5.1
python scripts/validate_release_metadata.py --expected 1.5.1
python -m pytest tests/regression/test_release_version_consistency.py -q
git diff --check
git tag -a v1.5.1 -m "Release v1.5.1"
git push origin v1.5.1
```

Pushing the tag starts `.github/workflows/build-release.yml`. The workflow creates a **draft**
GitHub release only after all required platform artifacts and `SHA256SUMS.txt` are present.
Review and smoke-test the attached artifacts before publishing the draft.

## Post-release

- [ ] Publish only the tested draft.
- [ ] Update the README download table from v1.2.0-beta.2 to v1.5.1.
- [ ] Mark the changelog entry with the actual release date.
- [ ] Record checksums and platform test results.
- [ ] Open the next `[Unreleased]` changelog section.
