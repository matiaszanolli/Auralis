# Auralis Documentation

**Last Updated:** October 22, 2025
**Version:** 2.0.0

Welcome to the Auralis documentation! This guide will help you find the information you need, whether you're a user, developer, or contributor.

---

## Quick Links

- **New to Auralis?** Start with the [README.md](README.md)
- **Want to develop?** Check [CLAUDE.md](CLAUDE.md) for architecture overview
- **Quick navigation?** See [DOCS_INDEX.md](DOCS_INDEX.md) for all documentation links
- **Detailed catalog?** Browse organized documentation in [docs/README.md](docs/README.md)

---

## Documentation Structure

### Core Documentation (Root Level)

**Essential files for everyone:**

- [README.md](README.md) - Main project introduction and quick start guide
- [CLAUDE.md](CLAUDE.md) - Comprehensive project overview, architecture, and development guide
- [DOCS_INDEX.md](DOCS_INDEX.md) - Quick navigation index to all documentation
- [DOCS.md](DOCS.md) - This file - Documentation overview

### Organized Documentation (docs/)

All detailed documentation is organized into categories under the `docs/` directory:

```
docs/
├── getting-started/         # User-facing documentation
├── development/             # Developer guides and architecture
├── design/                  # UI/UX design documentation
├── api/                     # API documentation and integration guides
├── deployment/              # Deployment and release documentation
└── archive/                 # Historical and obsolete documentation
```

---

## Documentation by Category

### 📖 Getting Started

*Location: [docs/getting-started/](docs/getting-started/)*

**For users and new developers:**
- Installation guides
- Quick start tutorials
- Basic usage examples

**Note:** This directory is currently being populated. For now, see [README.md](README.md)

---

### 🛠️ Development

*Location: [docs/development/](docs/development/)*

**Build and Development Guides:**
- [BUILD_QUICK_REFERENCE.md](docs/development/BUILD_QUICK_REFERENCE.md) - Quick reference for common build commands
- [STANDALONE_APP_BUILD_GUIDE.md](docs/development/STANDALONE_APP_BUILD_GUIDE.md) - Comprehensive guide for building standalone applications
- [TESTING_QUICKSTART.md](docs/development/TESTING_QUICKSTART.md) - Testing guide and test suite overview
- [NATIVE_FOLDER_PICKER.md](docs/development/NATIVE_FOLDER_PICKER.md) - Native OS folder picker implementation

**Architecture Documentation:**
- [audio_processing.md](docs/development/audio_processing.md) - Audio processing pipeline architecture
- [player_architecture.md](docs/development/player_architecture.md) - Audio player architecture
- [plugin_system.md](docs/development/plugin_system.md) - Plugin system design
- [ui_architecture.md](docs/development/ui_architecture.md) - UI architecture overview

**Docker Documentation:**
- [DOCKER.md](docs/development/DOCKER.md) - Docker overview
- [DOCKER_LINUX.md](docs/development/DOCKER_LINUX.md) - Docker on Linux
- [DOCKER_MACOS.md](docs/development/DOCKER_MACOS.md) - Docker on macOS
- [DOCKER_WINDOWS.md](docs/development/DOCKER_WINDOWS.md) - Docker on Windows
- [DOCKER_UPDATING.md](docs/development/DOCKER_UPDATING.md) - Docker update guide

---

### 🎨 Design

*Location: [docs/design/](docs/design/)*

**UI/UX Design Documentation:**
- [DESIGN_GUIDELINES.md](docs/design/DESIGN_GUIDELINES.md) - Comprehensive design guidelines and aesthetic
- [UI_IMPLEMENTATION_ROADMAP.md](docs/design/UI_IMPLEMENTATION_ROADMAP.md) - 6-week UI implementation plan with phases
- [UI_COMPONENTS_CHECKLIST.md](docs/design/UI_COMPONENTS_CHECKLIST.md) - Track progress on all 35+ UI components
- [QUICK_START_UI_DEVELOPMENT.md](docs/design/QUICK_START_UI_DEVELOPMENT.md) - Get started immediately with Phase 1 components
- [UI_SIMPLIFICATION.md](docs/design/UI_SIMPLIFICATION.md) - UI simplification philosophy and changes
- [ui_design.md](docs/design/ui_design.md) - Detailed UI design specifications

---

### 🔌 API

*Location: [docs/api/](docs/api/)*

**API and Integration Documentation:**
- [BACKEND_INTEGRATION_PLAN.md](docs/api/BACKEND_INTEGRATION_PLAN.md) - Backend integration planning
- [BACKEND_INTEGRATION_STATUS.md](docs/api/BACKEND_INTEGRATION_STATUS.md) - Integration status and progress
- [analyzer_api.md](docs/api/analyzer_api.md) - Analyzer API documentation
- [frequency_analyzer.md](docs/api/frequency_analyzer.md) - Frequency analyzer API

---

### 🚀 Deployment

*Location: [docs/deployment/](docs/deployment/)*

**Deployment and Release Documentation:**
- [LAUNCH_READINESS_CHECKLIST.md](docs/deployment/LAUNCH_READINESS_CHECKLIST.md) - Complete readiness assessment before launch
- [VERSION_SYSTEM_IMPLEMENTATION.md](docs/deployment/VERSION_SYSTEM_IMPLEMENTATION.md) - Version management system implementation details
- [VERSION_MIGRATION_ROADMAP.md](docs/deployment/VERSION_MIGRATION_ROADMAP.md) - Future migration planning and strategy

---

### 📦 Archive

*Location: [docs/archive/](docs/archive/)*

**Historical and Obsolete Documentation:**

The archive contains documentation from earlier development phases, completed milestones, and historical reference materials. These documents are preserved for historical context but are no longer actively maintained.

**Sub-categories:**
- `archive/phase-completions/` - UI phase completion reports (Phases 1-5)
- `archive/progress-reports/` - Daily/weekly progress summaries
- `archive/build-milestones/` - Build completion and fix reports

**Notable archived documents:**
- Legacy architecture plans
- Completed milestone reports
- Historical progress summaries
- Old build guides (superseded by current guides)
- Docker-era documentation (before web/Electron migration)

---

## Documentation Guidelines

### For Readers

**Finding Information:**
1. Start with [README.md](README.md) for project overview
2. Check [CLAUDE.md](CLAUDE.md) for comprehensive architecture
3. Browse category-specific docs in [docs/](docs/)
4. Check [PROJECT_STATUS.md](PROJECT_STATUS.md) for current state

**Documentation Hierarchy:**
- **README.md** - First stop for everyone
- **CLAUDE.md** - Deep dive into architecture and development
- **docs/** - Category-specific detailed documentation
- **Archive** - Historical reference only

### For Contributors

**When to Add Documentation:**
- **Major features** → Create detailed documentation in appropriate category
- **Breaking changes** → Update relevant guides and migration docs
- **Build changes** → Update build guides in `docs/development/`
- **API changes** → Update API docs in `docs/api/`
- **UI changes** → Update design docs in `docs/design/`

**When to Archive Documentation:**
- **Session summaries** → Archive after integration into PROJECT_STATUS.md
- **Milestone docs** → Archive after completion
- **Fix docs** → Archive after fix is verified and integrated
- **Redundant docs** → Archive after consolidation into main docs

**Where to Document:**
- **Architecture** → CLAUDE.md or `docs/development/`
- **Status/Progress** → PROJECT_STATUS.md
- **How-to guides** → Appropriate category in `docs/`
- **Future plans** → `docs/deployment/` or PROJECT_STATUS.md
- **Design specs** → `docs/design/`
- **API docs** → `docs/api/`

---

## Project Information

### Key Links

- **Repository:** https://github.com/matiaszanolli/Auralis
- **License:** GPL-3.0
- **Website:** Coming soon
- **Discord:** Coming soon

### Support

- **Issues:** [GitHub Issues](https://github.com/matiaszanolli/Auralis/issues)
- **Discussions:** [GitHub Discussions](https://github.com/matiaszanolli/Auralis/discussions)
- **Email:** Coming soon

---

## Quick Command Reference

### Development
```bash
# Web development
python launch-auralis-web.py --dev

# Desktop development
npm run dev

# Backend only
cd auralis-web/backend && python main.py
```

### Testing
```bash
# All tests
python -m pytest tests/ -v

# Specific test suites
python -m pytest tests/test_adaptive_processing.py -v
python -m pytest tests/backend/ -v
```

### Building
```bash
# Build all
npm run build

# Package desktop app
npm run package               # Current platform
npm run package:linux        # Linux
npm run package:win          # Windows
npm run package:mac          # macOS
```

---

## Documentation Statistics

**Total Documentation Files:** 50+
- Core Documentation: 4 files (root level)
- Development: 14 files
- Design: 6 files
- API: 4 files
- Deployment: 3 files
- Archive: 30+ files (historical reference)

**Last Major Reorganization:** October 18, 2025
- Organized 35+ root-level docs into categories
- Created clear documentation hierarchy
- Archived obsolete and historical documents
- Improved discoverability and navigation

---

**Maintained by:** Auralis Team
**Documentation Version:** 1.0.0
**Last Updated:** October 18, 2025
