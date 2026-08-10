# v1.5.1 Release Checklist

**State:** Prepared, blocked

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

- [ ] **REC-01:** one documented launcher owns each required child, installs nothing at runtime,
  reports real readiness, propagates one port, and shuts down only its own processes.
- [ ] **REC-02:** fresh and migrated databases both persist and reload fingerprints.
- [ ] **REC-03:** one-dimensional and `(samples, 1)` mono fixtures play in normal and enhanced
  modes without changing sample count or producing non-finite PCM.
- [ ] **REC-04 / #4426:** two rapid selections deterministically leave the second track active.
- [ ] `/api/ready` represents initialized engine/database state rather than process liveness.
- [ ] The full-stack smoke test is collected, isolated, uses an ephemeral port and temporary
  home/database, and fails when any required child fails.

## Required validation

- [x] Version consistency:

  ```bash
  python scripts/validate_release_metadata.py --expected 1.5.1
  python -m pytest tests/validation/test_release_version_consistency.py -q
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
- [ ] Python↔Rust boundary tests and the corrected Rust library gate pass.
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
- [ ] SHA-256 checksums are generated and verified for every published artifact.
- [ ] Version displayed by `/api/version`, Electron metadata, filenames, and release title is
  exactly `1.5.1`.
- [ ] Known limitations in the final GitHub release match the tested artifacts.

## Tag and publish

Only after all prior sections are green:

```bash
python sync_version.py 1.5.1
python scripts/validate_release_metadata.py --expected 1.5.1
python -m pytest tests/validation/test_release_version_consistency.py -q
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
