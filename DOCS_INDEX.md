# Auralis Documentation Index

**Last Updated:** September 30, 2025
**Version:** 1.0.0

This index provides quick access to all project documentation.

---

## 📚 Core Documentation

### [README.md](README.md)
**Main project readme** - Start here for project overview, features, and quick start guide.

### [CLAUDE.md](CLAUDE.md)
**Claude Code instructions** - Guidance for Claude Code when working with this repository. Contains:
- Project overview and architecture
- Essential commands (build, test, package)
- Key processing workflows
- Development guidelines
- Performance characteristics

### [PROJECT_STATUS.md](PROJECT_STATUS.md)
**Current project status** - Always up-to-date status of the project:
- Completed features
- Current metrics (test coverage, build sizes, performance)
- Next steps and roadmap
- Technology stack
- Documentation index

---

## 🔨 Build & Deployment

### [BUILD_QUICK_REFERENCE.md](BUILD_QUICK_REFERENCE.md)
**Quick build commands** - Fast reference for common build tasks:
- Development commands
- Build commands
- Package commands
- Testing commands

### [STANDALONE_APP_BUILD_GUIDE.md](STANDALONE_APP_BUILD_GUIDE.md)
**Detailed build guide** - Comprehensive guide for building standalone applications:
- Build architecture
- Step-by-step build process
- Packaging for different platforms
- Troubleshooting common issues

---

## 🔄 Version Management

### [VERSION_SYSTEM_IMPLEMENTATION.md](VERSION_SYSTEM_IMPLEMENTATION.md)
**Version system details** - Complete implementation of the version management system:
- How it works
- Migration process
- Backup system
- Developer guide
- Testing results

### [VERSION_MIGRATION_ROADMAP.md](VERSION_MIGRATION_ROADMAP.md)
**Migration strategy** - Future migration planning:
- Version numbering strategy
- Database schema versioning
- Migration file structure
- Testing strategy
- Rollback procedures

---

## 🚀 Launch Planning

### [LAUNCH_READINESS_CHECKLIST.md](LAUNCH_READINESS_CHECKLIST.md)
**Pre-launch checklist** - Complete readiness assessment:
- What's ready (features, testing, quality)
- What's needed (critical requirements)
- Launch scenarios (beta vs production)
- Risk assessment
- Recommended actions

---

## 📂 Documentation Organization

```
/mnt/data/src/matchering/
├── README.md                              # Start here!
├── CLAUDE.md                              # Claude Code instructions
├── PROJECT_STATUS.md                      # Current status
├── DOCS_INDEX.md                          # This file
│
├── BUILD_QUICK_REFERENCE.md              # Quick build commands
├── STANDALONE_APP_BUILD_GUIDE.md         # Detailed build guide
│
├── VERSION_SYSTEM_IMPLEMENTATION.md      # Version system details
├── VERSION_MIGRATION_ROADMAP.md          # Migration strategy
│
└── LAUNCH_READINESS_CHECKLIST.md         # Pre-launch checklist
```

---

## 🧪 Test Files

### Integration Tests (Root Directory)

**test_version_system.py**
- Tests version management system
- Validates migration functionality
- Checks database version tracking

**test_e2e_processing.py**
- End-to-end audio processing validation
- Tests all 5 presets (Adaptive, Gentle, Warm, Bright, Punchy)
- Audio quality verification

### Test Suite (tests/ Directory)

**tests/test_migrations.py** (12 tests)
- Migration manager tests
- Database backup/restore tests
- Version validation tests

**tests/backend/** (96 tests)
- API endpoint tests
- Processing engine tests
- WebSocket tests
- 74% coverage

**tests/test_adaptive_processing.py** (26 tests)
- Core processing tests
- Genre detection tests
- ML feature tests

---

## 🎯 Quick Links

### For New Developers
1. Start with [README.md](README.md)
2. Read [CLAUDE.md](CLAUDE.md) for architecture
3. Check [PROJECT_STATUS.md](PROJECT_STATUS.md) for current state

### For Building
1. [BUILD_QUICK_REFERENCE.md](BUILD_QUICK_REFERENCE.md) - Quick commands
2. [STANDALONE_APP_BUILD_GUIDE.md](STANDALONE_APP_BUILD_GUIDE.md) - Detailed guide

### For Deployment
1. [LAUNCH_READINESS_CHECKLIST.md](LAUNCH_READINESS_CHECKLIST.md) - Readiness check
2. [VERSION_SYSTEM_IMPLEMENTATION.md](VERSION_SYSTEM_IMPLEMENTATION.md) - Version management

### For Maintenance
1. [VERSION_MIGRATION_ROADMAP.md](VERSION_MIGRATION_ROADMAP.md) - Future migrations
2. [PROJECT_STATUS.md](PROJECT_STATUS.md) - Track progress

---

## 📊 Documentation Statistics

**Total Essential Documentation:** 9 files
- Core Documentation: 3 files
- Build & Deployment: 2 files
- Version Management: 2 files
- Launch Planning: 1 file
- Documentation Index: 1 file (this file)

**Total Test Files:** 3 root + test suite
**Total Coverage:** 108 tests passing (96 backend + 12 migration)

---

## 🧹 Cleanup History

**September 30, 2025:** Removed 16 obsolete documentation files
- Backend testing summaries (6 files)
- Session summaries (2 files)
- E2E testing doc (1 file)
- Build/integration docs (2 files)
- Temporary fix docs (2 files)
- Phase/milestone docs (2 files)
- Test files (1 file)

**Result:** 65% reduction in documentation, keeping only essential and current files.

---

## 💡 Documentation Guidelines

### When to Add New Documentation
- **Major features** - Create feature documentation
- **Breaking changes** - Update migration roadmap
- **Build changes** - Update build guides
- **API changes** - Update CLAUDE.md

### When to Remove Documentation
- **Session summaries** - Remove after integration into PROJECT_STATUS.md
- **Milestone docs** - Remove after completion
- **Fix docs** - Remove after fix is verified
- **Redundant docs** - Consolidate into existing docs

### Where to Document
- **Architecture** → CLAUDE.md
- **Status/Progress** → PROJECT_STATUS.md
- **How-to** → BUILD_QUICK_REFERENCE.md or STANDALONE_APP_BUILD_GUIDE.md
- **Future plans** → VERSION_MIGRATION_ROADMAP.md
- **Readiness** → LAUNCH_READINESS_CHECKLIST.md

---

**Maintained by:** Auralis Team
**Repository:** https://github.com/matiaszanolli/Auralis
**License:** GPL-3.0
