# Auralis Versioning Strategy

**Status:** Living reference

**Last reviewed:** 2026-07-24

**Current source version:** 1.5.1, unreleased recovery milestone

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
| Legacy product imports | `auralis/__version__.py` | Compatibility mirror, synchronized automatically |
| Python package metadata | `pyproject.toml` | Derived |
| Root/frontend/desktop package metadata | each `package.json` | Derived |
| Degraded backend fallback | `auralis-web/backend/routers/health.py` | Derived for builds missing the core import |
| Database schema | `auralis/__version__.py::__db_schema_version__` | Independent; bump only with a migration/schema change |
| Fingerprint algorithm | `auralis/__version__.py::FINGERPRINT_ALGORITHM_VERSION` | Independent; bump only when identical audio yields different fingerprints |

The backend imports the product version from `auralis/version.py` and the database schema
version from `auralis/__version__.py`. Do not use the compatibility mirror as a second
authority.

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
python -m pytest tests/validation/test_release_version_consistency.py -q
git diff --check
```

The synchronizer updates the canonical source, compatibility mirror, Python packaging,
JavaScript packages, and degraded backend fallback. Review the diff; it deliberately does not
edit changelogs, release notes, database schema, or fingerprint algorithm versions.

## Current state

- Source version: `1.5.1`
- Release state: prepared and blocked; no v1.5.1 tag or binaries
- Latest local source tag: `v1.2.1-beta.1`
- Latest documented binary release: `v1.2.0-beta.2`
- Database schema: `16`
- Fingerprint algorithm: `3`

The current release contract is:

- [v1.5.1 release notes](../releases/RELEASE_NOTES_1_5_1.md)
- [v1.5.1 release checklist](../releases/RELEASE_CHECKLIST_1_5_1.md)
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
tag against repository metadata and creates a draft GitHub release only after every required
artifact and checksum exists.

Because a pushed tag causes external build and release state:

- Do not tag a blocked candidate.
- Do not move or reuse a published tag.
- Do not publish the draft before artifact smoke tests.
- Prefer a new patch version after a bad published build.

The operational steps are maintained in [RELEASE_GUIDE.md](RELEASE_GUIDE.md).

## Changelog policy

The canonical changelog is [`docs/releases/CHANGELOG.md`](../releases/CHANGELOG.md) and follows
Keep a Changelog:

- Maintain one `[Unreleased]` section while work is in progress.
- Move it to `[X.Y.Z] - YYYY-MM-DD` only when the release is actually published.
- Describe user-visible behavior and compatibility effects.
- Put detailed implementation history in release notes or audits, not the top-level entry.

`docs/versions/CHANGELOG.md` is a legacy historical file and must not receive new release
history.
