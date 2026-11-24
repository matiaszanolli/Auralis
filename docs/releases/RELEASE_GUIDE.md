# Auralis Release Guide

This is the maintained procedure for preparing, building, and publishing an Auralis release.
The current candidate-specific gate is [RELEASE_CHECKLIST_1_5_1.md](RELEASE_CHECKLIST_1_5_1.md).
Version rules and the metadata registry are in [VERSIONING_STRATEGY.md](VERSIONING_STRATEGY.md).

## Release model

- `auralis/version.py` is the product-version source of truth.
- `sync_version.py` updates the derived `pyproject.toml`, `Dockerfile` label, and the root,
  frontend, and desktop `package.json` versions.
- Database schema and fingerprint algorithm versions are independent of the product version.
- A `v*` tag starts `.github/workflows/build-release.yml`.
- Successful Linux x64, Windows x64, and macOS Apple Silicon jobs create a **draft** GitHub
  release. A human publishes it only after testing the attached artifacts.
- That workflow is the **only** publisher of release artifacts and checksums. Never create a
  release or upload installers, `SHA256SUMS.txt` or electron-updater manifests (`latest*.yml`)
  from a workstation: a local build has none of the CI controls (SHA-pinned actions,
  hash-locked tooling, signed checksums, draft review), and the update manifests are what
  installed apps trust (#6529, #4905). The workflow does not upload `latest*.yml` today.
- Artifacts per release: `Auralis-X.Y.Z.AppImage`, `auralis-desktop_X.Y.Z_amd64.deb`, one
  `.flatpak`, `Auralis Setup X.Y.Z.exe`, `Auralis-X.Y.Z-arm64.dmg`, and `SHA256SUMS.txt`
  (plus `SHA256SUMS.txt.asc` when the GPG key is configured). The workflow fails when any is
  missing.
- JavaScript workspaces use pnpm; npm is not a supported release workflow.

## 1. Choose the version and scope

Use Semantic Versioning:

- Patch: backward-compatible fixes, documentation, or release hardening.
- Minor: backward-compatible features.
- Major: incompatible product/API changes.
- `-alpha.N`, `-beta.N`, or `-rc.N`: explicitly unstable prereleases.

Write the release entry before tagging. It must state what changed, known limitations,
compatibility or migration effects, and the evidence used to call the build ready.

## 2. Synchronize metadata

From the repository root:

```bash
python sync_version.py X.Y.Z
python scripts/validate_release_metadata.py --expected X.Y.Z
python -m pytest tests/regression/test_release_version_consistency.py -q
git diff --check
```

Review at least:

- `auralis/version.py`
- `pyproject.toml`
- the `LABEL version` line in `Dockerfile`
- root, frontend, and desktop `package.json`
- [CHANGELOG.md](CHANGELOG.md)
- candidate release notes and checklist

`scripts/validate_release_metadata.py` checks `auralis/version.py`, the three `package.json`
files, and `pyproject.toml`; the `Dockerfile` label is updated by `sync_version.py` but not
validated. Do not bump database schema or fingerprint algorithm versions for a product-only
release.

## 3. Pass the candidate’s release gate

The candidate checklist takes precedence over generic suite counts. CI baselines
(`pytest-baseline.json`, `pytest-slow-baseline.json`, and the frontend `test-baseline.json`)
fail on any new failure, so confirm the release commit's CI is green before starting. At minimum:

```bash
uv pip check

cd auralis-web/frontend
pnpm install --frozen-lockfile
pnpm run type-check:prod
pnpm run build
```

Then run the candidate’s targeted Python, frontend, Rust, and full-stack smoke gates. Use a
fresh temporary home/database for the end-to-end flow. A process being alive is not readiness:
the gate must wait for initialized engine and database state.

For v1.5.1, the full eleven-point
[definition of “working”](../audits/AUDIT_RECOVERY_2026-07-24.md#definition-of-working) is
mandatory. A red release blocker cannot be waived because unrelated broad suites are green.
The startup half of that gate is `tests/integration/test_application_startup.py`.

## 4. Prepare the release commit

Before committing:

- Confirm the changelog uses `[Unreleased]` while the candidate is still blocked.
- Confirm release notes do not claim untested platforms or fixed bugs.
- Confirm no logs, local databases, credentials, caches, or build outputs are staged.
- Confirm the working tree contains only intentional release changes.

Suggested commit:

```bash
git add <reviewed release files>
git commit -m "chore: prepare vX.Y.Z release"
```

Pushing a normal branch or commit does not create a release. Do not tag yet.

## 5. Create the tag

Only after every candidate gate is complete:

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

The tag is externally significant: it starts cross-platform builds and, when every required
artifact exists, creates a draft GitHub release. Never reuse or move a published tag. If an
unpublished build is bad, fix the defect and use the next appropriate version.

Before tagging, the same build matrix can be exercised with the workflow’s manual dispatch.
The required version input must exactly match `auralis/version.py`; manual runs upload workflow
artifacts but do not create a GitHub release. A push or pull request that touches the version
metadata files runs only the metadata preflight, not the platform builds.

## 6. Validate artifacts

Download artifacts from the draft release and test them on clean or representative systems:

- Linux x64: AppImage, Flatpak, and `.deb`
- Windows x64: installer, launch, upgrade/uninstall
- macOS Apple Silicon: ARM64 DMG

For each platform verify:

- Install and first launch
- Reported version and artifact filename
- Fresh database startup
- Library scan and persistence across restart
- Normal and enhanced playback, including mono
- Seek, queue, rapid switching, and WebSocket soak
- Clean shutdown without orphan children
- No uncaught UI error during the smoke flow

The workflow generates `SHA256SUMS.txt`; independently verify it before publishing. When the
repository secret `RELEASE_GPG_PRIVATE_KEY` is set, the workflow also writes a detached
signature, `SHA256SUMS.txt.asc`; otherwise it emits a warning and publishes the checksums
unsigned. The key fingerprint must be published out of band before the signature means anything.

No Windows Authenticode or Apple Developer ID signing or notarization is configured (#4905),
and `desktop/package.json` leaves update-signature verification, the hardened runtime, and
Gatekeeper assessment disabled. Do not present an unsigned Windows installer or an unsigned,
unnotarized DMG as a normal end-user release; state the limitation in the release notes.

## 7. Publish

Review the draft release:

- Tag, title, prerelease flag, and notes are correct.
- Every advertised artifact exists and was tested.
- Known limitations match the build.
- Checksums are present.

Publish only after that review. Then:

- Replace `[Unreleased]` with the actual release date.
- Open a fresh `[Unreleased]` changelog section.
- Update the README download table.
- Record platform results and checksums.

## Failed build or rollback

Do not force a broken artifact through the draft. Diagnose and fix it on a branch, repeat the
candidate gate, and tag the next appropriate version.

If a published release must be withdrawn, mark it as a draft or prerelease first, preserve an
incident record, and prepare a new patch version. Do not silently replace assets or move the
published tag.
