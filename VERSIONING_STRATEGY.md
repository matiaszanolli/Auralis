# Auralis Versioning Strategy & Release Management

**Status**: Beta Release Preparation
**Date**: October 24, 2025
**Current Version**: 0.8.0 (pre-beta)

## Executive Summary

This document defines the versioning standard, release process, and binary build triggers for Auralis as we approach the beta release milestone.

## Semantic Versioning Standard

Auralis follows **Semantic Versioning 2.0.0** (semver.org) with beta/alpha pre-release tags.

### Version Format

```
MAJOR.MINOR.PATCH[-PRERELEASE][+BUILDMETA]

Examples:
- 0.9.0-beta.1          # First beta release
- 0.9.0-beta.2          # Second beta with fixes
- 0.9.1-beta.1          # Beta with minor feature additions
- 1.0.0-rc.1            # Release candidate
- 1.0.0                 # First stable release
- 1.0.1                 # Patch release
- 1.1.0                 # Minor feature release
- 2.0.0                 # Major breaking changes
```

### Version Component Meanings

**MAJOR** (leftmost number):
- `0.x.x` = Pre-1.0 (alpha/beta/RC)
- `1.x.x` = First stable release
- `2.x.x+` = Breaking changes (API incompatibility, database schema changes requiring migration)

**MINOR** (middle number):
- New features (backward compatible)
- Significant improvements
- New processing modes or presets
- Major performance enhancements

**PATCH** (rightmost number):
- Bug fixes
- Performance improvements (minor)
- Documentation updates
- UI/UX tweaks (no new features)

**PRERELEASE** (optional suffix):
- `-alpha.N` = Early development, unstable
- `-beta.N` = Feature complete, testing phase
- `-rc.N` = Release candidate, final testing

**BUILDMETA** (optional suffix after +):
- `+20251024` = Build date
- `+linux.x64` = Platform info
- `+git.a1b2c3d` = Git commit hash

## Current Development Stage

### Where We Are Now

**Version**: `0.8.0` (internal development)

**Status**: Pre-beta, feature complete with optimizations

**Completed Major Features**:
- ✅ Adaptive mastering (core processing)
- ✅ All 4 dynamics behaviors
- ✅ Performance optimization (36.6x real-time)
- ✅ Library management with caching
- ✅ Web UI + Electron desktop
- ✅ Real-time player with processing
- ✅ Metadata editing
- ✅ Backend API (74% test coverage)

**Remaining for Beta**:
- Library scan UI (backend complete)
- Frontend test coverage expansion
- Version management system (this document)
- Beta testing with real users

## Beta Release Plan

### Version: 1.0.0-beta.1

**Target Date**: TBD (after completing beta checklist)

**Major Changes from 0.8.0**:
1. Performance optimization (36.6x real-time)
2. Numba JIT integration (40-70x envelope speedup)
3. Library scan API
4. Modular backend architecture
5. Large library support (50k+ tracks)

**Release Criteria** (Beta 1 Checklist):
- [ ] Library scan UI implemented
- [ ] Version management system active
- [ ] All integration tests passing (100%)
- [ ] Backend tests ≥ 75% coverage
- [ ] Frontend tests ≥ 50% coverage
- [ ] Desktop build successful (Linux .AppImage + .deb)
- [ ] Performance benchmarks documented
- [ ] User documentation complete
- [ ] Known issues documented

### Subsequent Beta Releases

**1.0.0-beta.2, beta.3, etc.**:
- Bug fixes from beta.1 testing
- Minor improvements
- No new features (feature freeze after beta.1)

**1.0.0-rc.1** (Release Candidate):
- No known critical bugs
- Performance validated
- Ready for final testing

**1.0.0** (Stable Release):
- All beta feedback addressed
- Production-ready
- Full documentation
- Marketing materials ready

## Version Management Implementation

### Single Source of Truth: `version.py`

**File**: `auralis/version.py`

```python
"""
Auralis version information.
Single source of truth for version across the entire project.
"""

__version__ = "1.0.0-beta.1"
__version_info__ = (1, 0, 0, "beta", 1)
__build_date__ = "2025-10-24"
__git_commit__ = "a1b2c3d"  # Auto-populated during build

# Version components for programmatic access
VERSION_MAJOR = 1
VERSION_MINOR = 0
VERSION_PATCH = 0
VERSION_PRERELEASE = "beta.1"  # Empty string for stable releases
VERSION_BUILD = ""  # Optional build metadata

# Semantic version string
SEMANTIC_VERSION = __version__

# User-friendly display version
DISPLAY_VERSION = f"Auralis v{__version__}"

# API version (for backward compatibility)
API_VERSION = "v1"

# Database schema version (independent of app version)
DB_SCHEMA_VERSION = 3

# Minimum compatible version (for upgrades)
MIN_COMPATIBLE_VERSION = "0.9.0"

def get_version() -> str:
    """Get the current version string."""
    return __version__

def get_version_info() -> dict:
    """Get detailed version information."""
    return {
        "version": __version__,
        "major": VERSION_MAJOR,
        "minor": VERSION_MINOR,
        "patch": VERSION_PATCH,
        "prerelease": VERSION_PRERELEASE,
        "build": VERSION_BUILD,
        "build_date": __build_date__,
        "git_commit": __git_commit__,
        "api_version": API_VERSION,
        "db_schema_version": DB_SCHEMA_VERSION,
    }

def is_compatible(version: str) -> bool:
    """Check if a version is compatible with current version."""
    from packaging.version import Version
    return Version(version) >= Version(MIN_COMPATIBLE_VERSION)
```

### Version Injection Points

**1. Package Metadata** (`pyproject.toml` or `setup.py`):
```toml
[project]
name = "auralis"
dynamic = ["version"]

[tool.setuptools.dynamic]
version = {attr = "auralis.version.__version__"}
```

**2. Frontend** (`auralis-web/frontend/package.json`):
```json
{
  "name": "auralis-frontend",
  "version": "1.0.0-beta.1",
  "scripts": {
    "version:sync": "node scripts/sync-version.js"
  }
}
```

**3. Electron** (`desktop/package.json`):
```json
{
  "name": "auralis-desktop",
  "version": "1.0.0-beta.1",
  "productName": "Auralis",
  "description": "Professional Adaptive Audio Mastering"
}
```

**4. Backend API Response** (`auralis-web/backend/routers/system.py`):
```python
from auralis.version import get_version_info

@router.get("/version")
def get_version():
    return get_version_info()
```

**5. UI Display** (Frontend components):
```typescript
// Fetch from API
const versionInfo = await fetch('/api/version').then(r => r.json())
// Display: "Auralis v1.0.0-beta.1"
```

## Binary Build Triggers

### Automated Build Conditions

Binaries (AppImage, .deb, .exe, .dmg) should be built automatically when:

**1. Version Tag Push** (Primary Trigger):
```bash
# Tag format: vMAJOR.MINOR.PATCH[-PRERELEASE]
git tag v1.0.0-beta.1
git push origin v1.0.0-beta.1
```

**Trigger**: CI/CD detects tag starting with `v`
**Action**: Build binaries for all platforms
**Artifacts**:
- `Auralis-1.0.0-beta.1.AppImage` (Linux)
- `auralis-desktop_1.0.0-beta.1_amd64.deb` (Debian/Ubuntu)
- `Auralis-Setup-1.0.0-beta.1.exe` (Windows)
- `Auralis-1.0.0-beta.1.dmg` (macOS)

**2. Release Branch Commits** (Optional):
```bash
# Commits to release/1.0.0-beta branch
git checkout -b release/1.0.0-beta
git push origin release/1.0.0-beta
```

**Trigger**: Push to `release/*` branch
**Action**: Build binaries for testing
**Artifacts**: Development builds (not for distribution)

**3. Manual Dispatch** (Development):
```yaml
# GitHub Actions workflow_dispatch
# Trigger: Manual button click in Actions tab
```

**Trigger**: Manual trigger in CI/CD
**Action**: Build binaries with custom parameters
**Use case**: Testing builds without creating tags

### Build Workflow

**File**: `.github/workflows/build-release.yml`

```yaml
name: Build Release Binaries

on:
  push:
    tags:
      - 'v*'  # Trigger on version tags (v1.0.0-beta.1, etc.)
  workflow_dispatch:  # Manual trigger

jobs:
  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Extract Version
        id: version
        run: |
          VERSION=${GITHUB_REF#refs/tags/v}
          echo "version=$VERSION" >> $GITHUB_OUTPUT

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install Dependencies
        run: |
          pip install -r requirements.txt
          cd desktop && npm install

      - name: Build Electron App
        run: |
          cd desktop
          npm run package:linux

      - name: Upload Artifacts
        uses: actions/upload-artifact@v3
        with:
          name: linux-binaries-${{ steps.version.outputs.version }}
          path: |
            desktop/dist/*.AppImage
            desktop/dist/*.deb

  build-windows:
    runs-on: windows-latest
    # Similar steps for Windows

  build-macos:
    runs-on: macos-latest
    # Similar steps for macOS

  create-release:
    needs: [build-linux, build-windows, build-macos]
    runs-on: ubuntu-latest
    steps:
      - name: Download All Artifacts
        uses: actions/download-artifact@v3

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          files: |
            **/*.AppImage
            **/*.deb
            **/*.exe
            **/*.dmg
          draft: true  # Create as draft for review
          prerelease: ${{ contains(github.ref, 'beta') || contains(github.ref, 'alpha') || contains(github.ref, 'rc') }}
```

## Release Process Workflow

### 1. Pre-Release Preparation

**Developer checklist**:
```bash
# 1. Ensure all changes committed
git status

# 2. Update version in version.py
# Edit auralis/version.py: __version__ = "1.0.0-beta.1"

# 3. Update CHANGELOG.md
# Add release notes

# 4. Sync versions across project
python scripts/sync_version.py  # Updates package.json files

# 5. Run full test suite
python -m pytest
cd auralis-web/frontend && npm test

# 6. Run benchmarks
python test_integration_quick.py
python benchmark_performance.py

# 7. Build locally to verify
cd desktop && npm run package:linux

# 8. Commit version bump
git add .
git commit -m "chore: bump version to 1.0.0-beta.1"
git push origin master
```

### 2. Release Tagging

```bash
# Create annotated tag
git tag -a v1.0.0-beta.1 -m "Release v1.0.0-beta.1

Features:
- Performance optimization (36.6x real-time)
- Numba JIT integration (40-70x envelope speedup)
- Library scan API
- Large library support

See CHANGELOG.md for full details."

# Push tag (triggers CI/CD builds)
git push origin v1.0.0-beta.1
```

### 3. CI/CD Build & Test

**Automated steps**:
1. ✅ Extract version from tag
2. ✅ Run test suite
3. ✅ Build binaries (Linux, Windows, macOS)
4. ✅ Run integration tests on built binaries
5. ✅ Create draft GitHub release
6. ✅ Upload artifacts

### 4. Release Review

**Manual steps**:
1. Download built binaries from GitHub Actions
2. Test on clean systems (VM or fresh install)
3. Verify:
   - Application launches
   - Core features work
   - Performance as expected
   - No critical bugs
4. Review draft release on GitHub
5. Edit release notes if needed

### 5. Publish Release

```bash
# If everything looks good:
# - Edit draft release on GitHub
# - Click "Publish release"

# Or via CLI:
gh release edit v1.0.0-beta.1 --draft=false
```

### 6. Post-Release

1. Update website/documentation with new version
2. Announce on social media / mailing list
3. Monitor for user reports
4. Create hotfix branch if critical bugs found

## Version Bump Script

**File**: `scripts/sync_version.py`

```python
#!/usr/bin/env python3
"""
Sync version across all project files.
Usage: python scripts/sync_version.py [NEW_VERSION]
"""

import re
import sys
from pathlib import Path

# Import version from single source of truth
import auralis.version as version

def update_package_json(file_path: Path, new_version: str):
    """Update version in package.json file."""
    content = file_path.read_text()
    updated = re.sub(
        r'"version":\s*"[^"]*"',
        f'"version": "{new_version}"',
        content
    )
    file_path.write_text(updated)
    print(f"✅ Updated {file_path}")

def update_version_py(new_version: str):
    """Update version.py with new version."""
    version_file = Path("auralis/version.py")
    content = version_file.read_text()

    # Parse new version
    match = re.match(r'(\d+)\.(\d+)\.(\d+)(?:-(.+))?', new_version)
    if not match:
        raise ValueError(f"Invalid version format: {new_version}")

    major, minor, patch, prerelease = match.groups()
    prerelease = prerelease or ""

    # Update __version__
    content = re.sub(
        r'__version__\s*=\s*"[^"]*"',
        f'__version__ = "{new_version}"',
        content
    )

    # Update VERSION_* constants
    content = re.sub(r'VERSION_MAJOR\s*=\s*\d+', f'VERSION_MAJOR = {major}', content)
    content = re.sub(r'VERSION_MINOR\s*=\s*\d+', f'VERSION_MINOR = {minor}', content)
    content = re.sub(r'VERSION_PATCH\s*=\s*\d+', f'VERSION_PATCH = {patch}', content)
    content = re.sub(
        r'VERSION_PRERELEASE\s*=\s*"[^"]*"',
        f'VERSION_PRERELEASE = "{prerelease}"',
        content
    )

    version_file.write_text(content)
    print(f"✅ Updated {version_file}")

def main():
    if len(sys.argv) > 1:
        new_version = sys.argv[1]
        # Validate version format
        if not re.match(r'^\d+\.\d+\.\d+(?:-[a-z0-9.]+)?$', new_version):
            print(f"❌ Invalid version format: {new_version}")
            print("Expected: MAJOR.MINOR.PATCH[-PRERELEASE]")
            sys.exit(1)

        print(f"📦 Bumping version to {new_version}")
        update_version_py(new_version)
    else:
        new_version = version.__version__
        print(f"📦 Syncing version {new_version} across project files")

    # Update all package.json files
    package_files = [
        Path("auralis-web/frontend/package.json"),
        Path("desktop/package.json"),
    ]

    for file_path in package_files:
        if file_path.exists():
            update_package_json(file_path, new_version)
        else:
            print(f"⚠️  File not found: {file_path}")

    print(f"\n✅ Version sync complete: v{new_version}")
    print("\nNext steps:")
    print("1. Review changes: git diff")
    print("2. Commit: git commit -am 'chore: bump version to {}'".format(new_version))
    print("3. Tag: git tag -a v{} -m 'Release v{}'".format(new_version, new_version))
    print("4. Push: git push origin master && git push origin v{}".format(new_version))

if __name__ == "__main__":
    main()
```

## Database Schema Versioning

**Independent from app version**: Database schema has its own version number.

**Current**: Schema v3 (with performance indexes)

**Schema Version Bumps**:
- v1 → v2: Added performance indexes
- v2 → v3: Added playlist support, metadata fields
- v3 → v4 (future): TBD

**Migration Strategy**:
```python
# auralis/library/migrations/migrate.py

SCHEMA_MIGRATIONS = {
    1: migrate_v1_to_v2,
    2: migrate_v2_to_v3,
    3: migrate_v3_to_v4,  # Future
}

def migrate_database(current_version: int, target_version: int):
    """Migrate database from current to target version."""
    for version in range(current_version, target_version):
        migration_func = SCHEMA_MIGRATIONS.get(version)
        if migration_func:
            migration_func()
```

## Changelog Format

**File**: `CHANGELOG.md`

```markdown
# Changelog

All notable changes to Auralis will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Features in development

### Changed
- Changes in development

### Fixed
- Fixes in development

## [1.0.0-beta.1] - 2025-10-24

### Added
- Performance optimization: 36.6x real-time processing
- Numba JIT compilation for 40-70x envelope speedup
- NumPy vectorization for 1.7x EQ speedup
- Parallel FFT processing for long audio (3.4x speedup)
- Library scan API endpoint with duplicate prevention
- Large library support (pagination, caching, indexes)
- Comprehensive performance benchmarking suite

### Changed
- Backend refactored to modular router architecture
- Graceful fallbacks for Numba (optional dependency)

### Fixed
- RMS boost overdrive on loud material
- Database performance with large libraries (50k+ tracks)

### Performance
- Overall pipeline: 2-3x faster
- Real-time factor: 36.6x on real-world audio
- Processes 1 hour of audio in ~98 seconds

## [0.8.0] - 2025-10-20

### Added
- All 4 dynamics behaviors (Heavy/Light Compression, Preserve/Expand Dynamics)
- Track metadata editing (14 editable fields)
- Backend modular router architecture

### Fixed
- Dynamics expansion behavior
- Crest factor accuracy (average 0.67 dB error)

[Unreleased]: https://github.com/matiaszanolli/Auralis/compare/v1.0.0-beta.1...HEAD
[1.0.0-beta.1]: https://github.com/matiaszanolli/Auralis/releases/tag/v1.0.0-beta.1
[0.8.0]: https://github.com/matiaszanolli/Auralis/releases/tag/v0.8.0
```

## Beta Release Checklist

### Pre-Beta (Current State)
- [x] Core processing complete
- [x] Performance optimization (36.6x real-time)
- [x] Backend API (74% coverage)
- [x] Library management
- [x] Desktop build working
- [x] Documentation comprehensive

### Beta 1 Requirements
- [ ] Create `auralis/version.py` with version info
- [ ] Create `scripts/sync_version.py` for version management
- [ ] Implement version tracking in database
- [ ] Add version endpoint to API
- [ ] Display version in UI
- [ ] Library scan UI implementation
- [ ] Frontend test coverage ≥ 50%
- [ ] Update CHANGELOG.md with beta.1 notes
- [ ] Create GitHub Actions workflow for builds
- [ ] Tag v1.0.0-beta.1 and test build process

### Release Candidate Requirements
- [ ] All beta feedback addressed
- [ ] No known critical bugs
- [ ] Performance validated across platforms
- [ ] Documentation complete and reviewed
- [ ] User guide written

### 1.0.0 Stable Requirements
- [ ] Extensive user testing (100+ hours)
- [ ] Marketing materials ready
- [ ] Website updated
- [ ] Launch announcement prepared

## Summary

**Versioning System**: Semantic Versioning 2.0.0
**Next Release**: 1.0.0-beta.1 (after completing beta checklist)
**Build Trigger**: Git tags starting with `v` (e.g., `v1.0.0-beta.1`)
**Version Source**: `auralis/version.py` (single source of truth)
**Release Process**: Tag → CI/CD Build → Test → Publish

**Immediate Next Steps**:
1. Create `auralis/version.py`
2. Create `scripts/sync_version.py`
3. Implement version tracking in database
4. Set up GitHub Actions build workflow
5. Complete beta checklist items

---

**Status**: Ready for implementation
**Target**: Beta 1 release
**Timeline**: 4-6 hours implementation + testing
