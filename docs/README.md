# Auralis Documentation Directory

This directory contains organized documentation for the Auralis project.

**For the main documentation index, see:** [DOCS.md](../DOCS.md) in the root directory.

---

## Directory Structure

```
docs/
├── README.md                     # This file
├── getting-started/              # User-facing documentation
├── development/                  # Developer guides and architecture
├── design/                       # UI/UX design documentation
├── api/                          # API documentation and integration guides
├── deployment/                   # Deployment and release documentation
└── archive/                      # Historical and obsolete documentation
    ├── phase-completions/        # UI phase completion reports
    ├── progress-reports/         # Daily/weekly progress summaries
    └── build-milestones/         # Build completion and fix reports
```

---

## Quick Navigation

### For Users
- **Getting Started:** [getting-started/](getting-started/) (coming soon)
- **Main README:** [../README.md](../README.md)

### For Developers
- **Architecture:** [../CLAUDE.md](../CLAUDE.md) (comprehensive overview)
- **Build Guides:** [development/](development/)
- **Testing:** [development/TESTING_QUICKSTART.md](development/TESTING_QUICKSTART.md)
- **API Docs:** [api/](api/)

### For Designers
- **Design Guidelines:** [design/DESIGN_GUIDELINES.md](design/DESIGN_GUIDELINES.md)
- **UI Roadmap:** [design/UI_IMPLEMENTATION_ROADMAP.md](design/UI_IMPLEMENTATION_ROADMAP.md)
- **Component Checklist:** [design/UI_COMPONENTS_CHECKLIST.md](design/UI_COMPONENTS_CHECKLIST.md)

### For Deployers
- **Launch Checklist:** [deployment/LAUNCH_READINESS_CHECKLIST.md](deployment/LAUNCH_READINESS_CHECKLIST.md)
- **Version Management:** [deployment/VERSION_SYSTEM_IMPLEMENTATION.md](deployment/VERSION_SYSTEM_IMPLEMENTATION.md)

---

## Documentation Categories

### 📖 Getting Started
*Location: [getting-started/](getting-started/)*

User-facing documentation for installation, setup, and basic usage.

**Status:** Directory created, content coming soon. For now, see [../README.md](../README.md)

---

### 🛠️ Development
*Location: [development/](development/)*

Comprehensive developer documentation including build guides, architecture docs, and Docker setup.

**Key Documents:**
- [BUILD_QUICK_REFERENCE.md](development/BUILD_QUICK_REFERENCE.md) - Quick command reference
- [STANDALONE_APP_BUILD_GUIDE.md](development/STANDALONE_APP_BUILD_GUIDE.md) - Complete build guide
- [TESTING_QUICKSTART.md](development/TESTING_QUICKSTART.md) - Testing guide
- [audio_processing.md](development/audio_processing.md) - Audio processing architecture
- [player_architecture.md](development/player_architecture.md) - Player architecture

---

### 🎨 Design
*Location: [design/](design/)*

UI/UX design documentation, component specifications, and implementation roadmaps.

**Key Documents:**
- [DESIGN_GUIDELINES.md](design/DESIGN_GUIDELINES.md) - Complete design guidelines
- [UI_IMPLEMENTATION_ROADMAP.md](design/UI_IMPLEMENTATION_ROADMAP.md) - 6-week implementation plan
- [UI_COMPONENTS_CHECKLIST.md](design/UI_COMPONENTS_CHECKLIST.md) - Component tracking
- [QUICK_START_UI_DEVELOPMENT.md](design/QUICK_START_UI_DEVELOPMENT.md) - Quick start guide

---

### 🔌 API
*Location: [api/](api/)*

API documentation and integration guides for backend services and analyzers.

**Key Documents:**
- [BACKEND_INTEGRATION_PLAN.md](api/BACKEND_INTEGRATION_PLAN.md) - Integration planning
- [BACKEND_INTEGRATION_STATUS.md](api/BACKEND_INTEGRATION_STATUS.md) - Integration status
- [analyzer_api.md](api/analyzer_api.md) - Analyzer API reference
- [frequency_analyzer.md](api/frequency_analyzer.md) - Frequency analyzer API

---

### 🚀 Deployment
*Location: [deployment/](deployment/)*

Deployment guides, version management, and launch checklists.

**Key Documents:**
- [LAUNCH_READINESS_CHECKLIST.md](deployment/LAUNCH_READINESS_CHECKLIST.md) - Pre-launch checklist
- [VERSION_SYSTEM_IMPLEMENTATION.md](deployment/VERSION_SYSTEM_IMPLEMENTATION.md) - Version management
- [VERSION_MIGRATION_ROADMAP.md](deployment/VERSION_MIGRATION_ROADMAP.md) - Migration strategy

---

### 📦 Archive
*Location: [archive/](archive/)*

Historical documentation from earlier development phases. Preserved for reference but not actively maintained.

**Sub-categories:**
- [archive/phase-completions/](archive/phase-completions/) - UI development phase reports (1-5)
- [archive/progress-reports/](archive/progress-reports/) - Daily/weekly progress summaries
- [archive/build-milestones/](archive/build-milestones/) - Build completion reports

**Note:** Archive documents are for historical reference only. For current information, see the active documentation categories above.

---

## Contributing to Documentation

### Adding New Documentation

1. **Determine the category** - Choose the appropriate directory based on content
2. **Create the document** - Use Markdown format, follow existing naming conventions
3. **Update this README** - Add a link to your new document in the appropriate section
4. **Update DOCS.md** - Add entry to the main documentation index in the root directory

### Archiving Old Documentation

1. **Move to archive/** - Place in appropriate sub-category (phase-completions, progress-reports, etc.)
2. **Update references** - Remove from active documentation indexes
3. **Preserve links** - Update any references to archived documents

### Documentation Standards

- **Format:** Markdown (.md files)
- **Naming:** Use descriptive names with underscores or hyphens (e.g., `BUILD_QUICK_REFERENCE.md`)
- **Headers:** Use clear, hierarchical headers (##, ###, etc.)
- **Links:** Use relative links to other documentation
- **Status:** Include status badges or date stamps where appropriate

---

## Finding Information

### By Topic

- **Installation & Setup** → [getting-started/](getting-started/) or [../README.md](../README.md)
- **Building & Testing** → [development/](development/)
- **Architecture** → [../CLAUDE.md](../CLAUDE.md) or [development/](development/)
- **UI Design** → [design/](design/)
- **API Integration** → [api/](api/)
- **Deployment** → [deployment/](deployment/)
- **Historical Info** → [archive/](archive/)

### By Role

- **New User** → Start with [../README.md](../README.md)
- **Developer** → See [../CLAUDE.md](../CLAUDE.md) then [development/](development/)
- **Designer** → See [design/](design/)
- **DevOps** → See [deployment/](deployment/) and [development/DOCKER.md](development/DOCKER.md)
- **Contributor** → See [../CLAUDE.md](../CLAUDE.md) and [../PROJECT_STATUS.md](../PROJECT_STATUS.md)

---

## Documentation Statistics

- **Active Documentation:** 30+ files across 5 categories
- **Archived Documentation:** 30+ historical files
- **Last Major Reorganization:** October 18, 2025
- **Primary Language:** English
- **Format:** Markdown

---

**Need help?** Open an issue on [GitHub](https://github.com/matiaszanolli/Auralis/issues) or check the main [DOCS.md](../DOCS.md) index.

**Maintained by:** Auralis Team
**Last Updated:** October 18, 2025
