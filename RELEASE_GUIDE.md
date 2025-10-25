# Auralis Release Guide

**Quick Reference**: How to release a new version of Auralis

## Prerequisites

- [ ] All features complete and tested
- [ ] All tests passing (`python -m pytest`)
- [ ] Performance benchmarks run and documented
- [ ] CHANGELOG.md updated with release notes
- [ ] Known issues documented
- [ ] GitHub Actions configured (`.github/workflows/build-release.yml`)
- [ ] Git repository clean (`git status` shows no uncommitted changes)

## Release Checklist

### Step 1: Pre-Release Testing (1-2 hours)

```bash
# 1. Run full test suite
python -m pytest --cov=auralis --cov-report=html tests/ -v
cd auralis-web/frontend && npm test

# 2. Run performance benchmarks
python test_integration_quick.py
python benchmark_performance.py

# 3. Build locally to verify
cd desktop
npm run package:linux  # Or package:win / package:mac

# 4. Test built binary
./dist/Auralis-*.AppImage  # Launch and do smoke testing
```

**Smoke Test Checklist**:
- [ ] Application launches without errors
- [ ] Can add folder to library
- [ ] Can play audio
- [ ] Processing works (enhanced playback)
- [ ] Settings save/load correctly
- [ ] Performance is as expected (36.6x real-time)

### Step 2: Version Bump (10 minutes)

```bash
# Decide on version number
# Format: MAJOR.MINOR.PATCH[-PRERELEASE]
# Examples:
#   - 1.0.0-beta.1  (first beta)
#   - 1.0.0-beta.2  (beta with fixes)
#   - 1.0.0-rc.1    (release candidate)
#   - 1.0.0         (stable release)

# Bump version across all files
python scripts/sync_version.py 1.0.0-beta.1

# Review changes
git diff

# Verify version in key files
cat auralis/version.py | grep __version__
cat desktop/package.json | grep version
cat auralis-web/frontend/package.json | grep version
```

### Step 3: Update CHANGELOG (15 minutes)

Edit `CHANGELOG.md`:

```markdown
## [1.0.0-beta.1] - 2025-10-24

### Added
- List new features

### Changed
- List changes

### Fixed
- List bug fixes

### Performance
- List performance improvements
```

### Step 4: Commit Version Bump (5 minutes)

```bash
# Stage all version changes
git add auralis/version.py
git add desktop/package.json
git add auralis-web/frontend/package.json
git add CHANGELOG.md

# Commit with standardized message
git commit -m "chore: bump version to 1.0.0-beta.1

Preparing for beta.1 release with:
- Performance optimization (36.6x real-time)
- Version management system
- Library scan API

See CHANGELOG.md for full details."

# Push to master
git push origin master
```

### Step 5: Create Git Tag (5 minutes)

```bash
# Create annotated tag
git tag -a v1.0.0-beta.1 -m "Release v1.0.0-beta.1

Features:
- Performance optimization (36.6x real-time)
- Numba JIT integration (40-70x envelope speedup)
- Library scan API backend
- Version management system

Improvements:
- 2-3x faster processing pipeline
- Large library support (50k+ tracks)
- Modular backend architecture

See CHANGELOG.md for full details."

# Push tag to trigger CI/CD builds
git push origin v1.0.0-beta.1
```

**Important**: Pushing the tag triggers automated builds in GitHub Actions!

### Step 6: Monitor CI/CD Build (30-60 minutes)

1. Go to GitHub Actions: https://github.com/matiaszanolli/Auralis/actions
2. Find the "Build Release Binaries" workflow
3. Monitor build progress:
   - Linux build (AppImage + .deb)
   - Windows build (.exe)
   - macOS build (.dmg)

**If build fails**:
```bash
# Delete tag locally and remotely
git tag -d v1.0.0-beta.1
git push origin :refs/tags/v1.0.0-beta.1

# Fix the issue
# ... make fixes ...

# Commit fix
git commit -am "fix: <issue description>"
git push origin master

# Re-create tag
git tag -a v1.0.0-beta.1 -m "..."
git push origin v1.0.0-beta.1
```

### Step 7: Download & Test Artifacts (30 minutes)

Once CI/CD completes:

1. Download artifacts from GitHub Actions
2. Test each platform binary:
   - Linux: `chmod +x Auralis-*.AppImage && ./Auralis-*.AppImage`
   - Windows: Run .exe installer
   - macOS: Open .dmg and drag to Applications

**Test on clean systems** (VM or fresh install recommended):
- [ ] Application installs correctly
- [ ] All features work
- [ ] Performance is good (36.6x real-time)
- [ ] No critical bugs

### Step 8: Review Draft Release (15 minutes)

1. Go to GitHub Releases: https://github.com/matiaszanolli/Auralis/releases
2. Find draft release created by CI/CD
3. Review:
   - [ ] Version number correct
   - [ ] Release title correct
   - [ ] Release notes accurate and complete
   - [ ] All binaries attached (Linux, Windows, macOS)
   - [ ] Prerelease flag set correctly (for beta/rc)

4. Edit release notes if needed:
   - Add screenshots
   - Add installation instructions
   - Highlight key features
   - Link to documentation

### Step 9: Publish Release (5 minutes)

**Final checks before publishing**:
- [ ] All artifacts tested and working
- [ ] Release notes accurate and complete
- [ ] Known issues documented
- [ ] Version correct

**Publish**:
1. Click "Publish release" button
2. OR via CLI: `gh release edit v1.0.0-beta.1 --draft=false`

### Step 10: Post-Release Activities (1-2 hours)

**Update documentation**:
```bash
# Update main README if needed
git checkout -b docs/release-1.0.0-beta.1
# ... edit README.md ...
git commit -am "docs: update README for v1.0.0-beta.1"
git push origin docs/release-1.0.0-beta.1
# Create PR, review, merge
```

**Announce release**:
- [ ] Update project website (if exists)
- [ ] Post on social media
- [ ] Send to mailing list (if exists)
- [ ] Update documentation site

**Monitor for issues**:
- [ ] Watch GitHub Issues for bug reports
- [ ] Monitor user feedback
- [ ] Prepare hotfix branch if critical bugs found

## Hotfix Release Process

If critical bug found in release:

```bash
# Create hotfix branch from release tag
git checkout -b hotfix/1.0.0-beta.1-fix v1.0.0-beta.1

# Fix the bug
# ... make fixes ...
git commit -am "fix: critical bug description"

# Bump to patch or next beta
python scripts/sync_version.py 1.0.0-beta.2
git commit -am "chore: bump version to 1.0.0-beta.2"

# Merge back to master
git checkout master
git merge hotfix/1.0.0-beta.1-fix
git push origin master

# Tag and release
git tag -a v1.0.0-beta.2 -m "Hotfix release..."
git push origin v1.0.0-beta.2

# Delete hotfix branch
git branch -d hotfix/1.0.0-beta.1-fix
```

## Release Schedule

### Beta Phase (1.0.0-beta.x)

**Beta.1** (Current):
- All features complete
- Performance optimized
- Library management working
- Desktop builds ready

**Beta.2, Beta.3, etc.** (As needed):
- Bug fixes only
- Minor improvements
- Performance tuning
- UI polish

**Release Cadence**: Weekly or bi-weekly

### Release Candidate (1.0.0-rc.x)

**RC.1**:
- All beta feedback addressed
- No known critical bugs
- Final testing phase

**RC.2, etc.** (If needed):
- Only critical fixes
- Final polish

**Release Cadence**: 1-2 weeks after final beta

### Stable Release (1.0.0)

**1.0.0**:
- Production ready
- Extensive testing complete (100+ hours)
- All platforms supported
- Full documentation
- Marketing ready

**Target**: 4-6 weeks after beta.1

## Version Numbering Examples

**Pre-1.0 (Current)**:
- `0.8.0` - Internal development
- `0.9.0-alpha.1` - Early alpha (if needed)
- `1.0.0-beta.1` - First beta ← **We are here**
- `1.0.0-beta.2` - Second beta (bug fixes)
- `1.0.0-rc.1` - Release candidate
- `1.0.0` - First stable release

**Post-1.0 (Future)**:
- `1.0.1` - Patch (bug fixes)
- `1.1.0` - Minor (new features, backward compatible)
- `2.0.0` - Major (breaking changes)

## Common Issues

### "Tag already exists"
```bash
# Delete local tag
git tag -d v1.0.0-beta.1

# Delete remote tag
git push origin :refs/tags/v1.0.0-beta.1

# Recreate
git tag -a v1.0.0-beta.1 -m "..."
git push origin v1.0.0-beta.1
```

### "CI/CD build failed"
1. Check GitHub Actions logs
2. Fix the issue locally
3. Delete tag and re-tag (see above)
4. Or create new patch version (1.0.0-beta.2)

### "Binary doesn't work"
1. Test on clean system (not development machine)
2. Check for missing dependencies
3. Verify Python/Node versions in CI/CD
4. Check Electron build configuration

### "Version mismatch"
```bash
# Re-sync version across all files
python scripts/sync_version.py

# Verify
git diff
```

## Tools & Commands Reference

### Version Management
```bash
# Bump version
python scripts/sync_version.py <NEW_VERSION>

# Check current version
python -c "from auralis.version import get_version; print(get_version())"

# Get version info (JSON)
python auralis/version.py
```

### Git Tagging
```bash
# List all tags
git tag -l

# Show tag details
git show v1.0.0-beta.1

# Delete tag
git tag -d <TAG_NAME>
git push origin :refs/tags/<TAG_NAME>
```

### GitHub CLI (gh)
```bash
# View releases
gh release list

# View specific release
gh release view v1.0.0-beta.1

# Edit release
gh release edit v1.0.0-beta.1 --draft=false

# Delete release
gh release delete v1.0.0-beta.1
```

### Building Locally
```bash
# Linux
cd desktop && npm run package:linux

# Windows (on Windows machine)
cd desktop && npm run package:win

# macOS (on macOS machine)
cd desktop && npm run package:mac

# All platforms (requires proper setup)
cd desktop && npm run package
```

## Emergency Rollback

If release has critical issues and needs to be pulled:

1. **Un-publish release on GitHub**:
   - Go to Releases page
   - Click "Edit" on problematic release
   - Check "Set as a pre-release" or "Save draft"

2. **Delete tag** (if needed):
   ```bash
   git push origin :refs/tags/v1.0.0-beta.1
   ```

3. **Fix issues**:
   - Create hotfix branch
   - Fix bugs
   - Test thoroughly

4. **Release fixed version**:
   - Bump to next version (e.g., 1.0.0-beta.2)
   - Follow normal release process

## Success Criteria

**Release is successful if**:
- [ ] All binaries build without errors
- [ ] All binaries install and launch correctly
- [ ] No critical bugs reported in first 24 hours
- [ ] Performance meets expectations (36.6x real-time)
- [ ] User feedback is positive

**Release needs hotfix if**:
- [ ] Critical bugs affecting core functionality
- [ ] Crashes or data loss
- [ ] Major performance regressions
- [ ] Security vulnerabilities

## Documentation

**Key documents**:
- [VERSIONING_STRATEGY.md](VERSIONING_STRATEGY.md) - Versioning standard and strategy
- [CHANGELOG.md](CHANGELOG.md) - Release history and notes
- [PERFORMANCE_OPTIMIZATION_QUICK_START.md](PERFORMANCE_OPTIMIZATION_QUICK_START.md) - Performance info
- This file (RELEASE_GUIDE.md) - Release process

**For users**:
- Installation instructions in release notes
- [README.md](README.md) - Project overview
- [CLAUDE.md](CLAUDE.md) - Developer documentation

---

## Quick Release Checklist (TL;DR)

For experienced maintainers:

```bash
# 1. Test everything
python -m pytest && python benchmark_performance.py

# 2. Bump version
python scripts/sync_version.py 1.0.0-beta.1

# 3. Update CHANGELOG
vim CHANGELOG.md

# 4. Commit & tag
git commit -am "chore: bump version to 1.0.0-beta.1"
git push origin master
git tag -a v1.0.0-beta.1 -m "Release v1.0.0-beta.1"
git push origin v1.0.0-beta.1

# 5. Monitor CI/CD
# https://github.com/matiaszanolli/Auralis/actions

# 6. Test artifacts, publish release
# https://github.com/matiaszanolli/Auralis/releases
```

**Time estimate**: 2-4 hours for full release cycle

---

**Questions?** See [VERSIONING_STRATEGY.md](VERSIONING_STRATEGY.md) for detailed information.
