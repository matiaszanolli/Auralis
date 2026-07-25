# Auralis Release Guide

This is the maintained procedure for preparing, building, and publishing an Auralis release.
The current candidate-specific gate is
[RELEASE_CHECKLIST_1_5_1.md](../releases/RELEASE_CHECKLIST_1_5_1.md).

## Release model

- `auralis/version.py` is the product-version source of truth.
- `sync_version.py` updates derived Python, backend fallback, packaging, root package,
  frontend, and desktop metadata.
- Database schema and fingerprint algorithm versions are independent of the product version.
- A `v*` tag starts `.github/workflows/build-release.yml`.
- Successful Linux x64, Windows x64, and macOS Apple Silicon jobs create a **draft** GitHub
  release. A human publishes it only after testing the attached artifacts.
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
python -m pytest tests/validation/test_release_version_consistency.py -q
git diff --check
```

Review at least:

- `auralis/version.py`
- `auralis/__version__.py` compatibility exports
- `pyproject.toml`
- root, frontend, and desktop `package.json`
- the degraded `/api/version` fallback
- `docs/releases/CHANGELOG.md`
- candidate release notes and checklist

Do not bump database schema or fingerprint algorithm versions for a product-only release.

## 3. Pass the candidate’s release gate

The candidate checklist takes precedence over generic suite counts. At minimum:

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
artifacts but do not create a GitHub release.

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

The workflow generates `SHA256SUMS.txt`; independently verify it before publishing.

CI macOS builds are ad-hoc signed unless Apple signing and notarization credentials are
configured. Do not present an unsigned and unnotarized DMG as a normal end-user release.

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
