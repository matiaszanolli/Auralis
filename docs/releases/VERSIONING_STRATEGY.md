# Auralis Versioning Strategy

**Status:** Living reference

## Principles

Auralis follows Semantic Versioning 2.0.0 for the product version:

```text
MAJOR.MINOR.PATCH[-PRERELEASE]
```

- **MAJOR:** incompatible product or API change.
- **MINOR:** backward-compatible feature release.
- **PATCH:** backward-compatible fixes, release hardening, or documentation.
- **PRERELEASE:** `alpha.N`, `beta.N`, or `rc.N`.

Build metadata is valid SemVer but is not currently accepted by `sync_version.py`; add support
to the tool before using it in a release version.

## Version source-of-truth registry

| Concern | Authority | Notes |
|---------|-----------|-------|
| Product version | `auralis/version.py` | Human-authored source of truth |
| Python package metadata | `pyproject.toml` | Derived |
| Container image label | `Dockerfile` (`LABEL version`) | Derived |
| Root/frontend/desktop package metadata | each `package.json` | Derived |
| Database schema | `auralis/__version__.py::__db_schema_version__` | Independent; bump only with a migration/schema change |
| Fingerprint algorithm | `auralis/__version__.py::FINGERPRINT_ALGORITHM_VERSION` | Independent; bump only when identical audio yields different fingerprints |

The backend reports the product version from `auralis/version.py`, which re-exports the
database schema version from `auralis/__version__.py`. That module holds only the two independent
data-format versions; it has no product-version mirror, so do not treat it as a second authority.

## Selecting a version

Choose the smallest version that communicates compatibility:

- `1.5.1`: fixes and recovery hardening after the 1.5.0 source milestone.
- `1.6.0`: backward-compatible product features.
- `2.0.0`: incompatible contract or migration policy.
- `1.5.1-rc.1`: a release candidate that still requires final artifact validation.

A database migration does not automatically require a product major version. Judge the
product/API compatibility separately, while always bumping and migrating the schema version.

## Source version is not release status

These states are distinct:

1. **Prepared source:** metadata and changelog identify the intended version.
2. **Release-ready:** the candidate-specific checklist is green.
3. **Tagged:** an immutable `vX.Y.Z` tag exists.
4. **Built:** all required platform jobs produced artifacts.
5. **Drafted:** CI created a GitHub draft release.
6. **Published:** tested artifacts and final notes are public.

Documentation must say which state applies. A version bump alone must never be described as
shipped, stable, or production-ready.

## Synchronizing a version

From any working directory:

```bash
python /path/to/Auralis/sync_version.py X.Y.Z[-prerelease]
```

From the repository root:

```bash
python sync_version.py 1.5.1
python -m pytest tests/regression/test_release_version_consistency.py -q
git diff --check
```

The synchronizer updates the canonical source, `pyproject.toml`, the `Dockerfile` label, and
the three `package.json` files. Review the diff; it deliberately does not edit changelogs,
release notes, database schema, or fingerprint algorithm versions.
`scripts/validate_release_metadata.py` is the dependency-free check that the canonical source,
`pyproject.toml`, and the `package.json` files agree.

## Current release state

The release checklist and notes for the current candidate record its state, its latest tag
(`git tag`), and its latest published binary release:

- [v1.5.1 release notes](RELEASE_NOTES_1_5_1.md)
- [v1.5.1 release checklist](RELEASE_CHECKLIST_1_5_1.md)
- [working-state recovery audit](../audits/AUDIT_RECOVERY_2026-07-24.md)

## Release gates

Every release requires:

- Consistent version metadata.
- Accurate changelog and candidate notes.
- A clean candidate-specific automated gate.
- A fresh-install/fresh-database end-to-end smoke.
- Tested artifacts for every advertised platform.
- Documented known limitations and checksums.

For v1.5.1, the audit’s eleven-point definition of “working” is mandatory. The project does
not need every historical test or static-analysis finding cleared for this milestone, but no
known high-severity working-state blocker may remain.

## Tag and build behavior

Tags matching `v*` start `.github/workflows/build-release.yml`. The workflow builds Linux x64
AppImage, Flatpak, and `.deb`, Windows x64, and macOS Apple Silicon artifacts. It validates the
tag against repository metadata with `scripts/validate_release_metadata.py` and creates a draft
GitHub release only after every required artifact and `SHA256SUMS.txt` exist. A prerelease
version (`-alpha.N`, `-beta.N`, `-rc.N`) marks the draft as a prerelease. CI is the only release
publisher (#6529); the artifact list, signing status, and checksum handling are in
[RELEASE_GUIDE.md](RELEASE_GUIDE.md).

Because a pushed tag causes external build and release state:

- Do not tag a blocked candidate.
- Do not move or reuse a published tag.
- Do not publish the draft before artifact smoke tests.
- Prefer a new patch version after a bad published build.

The operational steps are maintained in [RELEASE_GUIDE.md](RELEASE_GUIDE.md).

## Changelog policy

The canonical changelog is [`docs/releases/CHANGELOG.md`](CHANGELOG.md) and follows
Keep a Changelog:

- Maintain one `[Unreleased]` section while work is in progress.
- Move it to `[X.Y.Z] - YYYY-MM-DD` only when the release is actually published.
- Describe user-visible behavior and compatibility effects.
- Put detailed implementation history in release notes or audits, not the top-level entry.

`docs/archive/roadmaps/LEGACY_CHANGELOG.md` is a legacy historical file and must not receive new release
history.
