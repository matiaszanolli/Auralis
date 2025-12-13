# Auralis Documentation

Complete documentation for the Auralis audio processing and music player project.

## 📚 Documentation Structure

### 🎯 [Getting Started](getting-started/)
Quick start guides and setup instructions for new developers and users.

- **[BETA_USER_GUIDE.md](getting-started/BETA_USER_GUIDE.md)** - User guide for beta release

### 🏗️ [Development](development/)
Core development documentation, standards, and setup guides.

- **[TESTING_GUIDELINES.md](development/TESTING_GUIDELINES.md)** - Test quality standards & invariant testing philosophy (MANDATORY READ)
- **[DEVELOPMENT_SETUP_BACKEND.md](development/DEVELOPMENT_SETUP_BACKEND.md)** - Backend environment setup + **Phase 5 Pytest Fixtures Guide** ✨
- **[DEVELOPMENT_SETUP_FRONTEND.md](development/DEVELOPMENT_SETUP_FRONTEND.md)** - Frontend environment setup + Phase 5 test integration
- **[DEVELOPMENT_STANDARDS.md](development/DEVELOPMENT_STANDARDS.md)** - Complete coding standards (Python & TypeScript)

### 📊 [Phases](phases/)
Development phase documentation organized by phase number and type.

- **[Phase 1-10](phases/phase-1-10/)** - Core feature development phases
- **[Phase 25](phases/phase-25/)** - Specialized audio processing phases
- **[Phases A-C](phases/phases-a-c/)** - UI modernization and refactoring phases

See [phases/README.md](phases/README.md) for detailed phase information.

### 🔧 [Refactoring](refactoring/)
Documentation of refactoring efforts, code improvements, and architectural changes.

- **[Completion Reports](refactoring/completion-reports/)** - Detailed refactoring completion documents
- **[Plans](refactoring/plans/)** - Refactoring plans and strategies

See [refactoring/README.md](refactoring/README.md) for refactoring documentation index.

### ⚡ [Features](features/)
Feature-specific documentation covering major components and systems.

- **[Adaptive Mastering](features/adaptive-mastering/)** - Audio enhancement algorithms
- **[Audio Processing](features/audio-processing/)** - DSP pipeline and optimization
- **[Backend API](features/backend-api/)** - REST API enhancements
- **[Cache System](features/cache-system/)** - Two-tier caching strategy
- **[Multistyle Analysis](features/multistyle-analysis/)** - Multi-genre audio analysis
- **[Priority 4 Work](features/priority-4-work/)** - High-priority features

### 🎨 [Frontend](frontend/)
React/TypeScript frontend documentation and components.

- **[Testing](frontend/testing/)** - Frontend test guides and memory management
- **[Analysis](frontend/analysis/)** - Component analysis and patterns
- **[Components](frontend/components/)** - Component documentation
- **[Implementation](frontend/implementation/)** - Implementation guides

See [frontend/README.md](frontend/README.md) for frontend documentation index.

### ⚙️ [Optimization](optimization/)
Performance optimization documentation.

### 📅 [Sessions](sessions/)
Session notes from development meetings.

## 🎯 Key Documentation Paths

- **Architecture Guide**: [../CLAUDE.md](../CLAUDE.md) - Complete technical reference
- **Master Roadmap**: [MASTER_ROADMAP.md](MASTER_ROADMAP.md) - Project roadmap
- **Testing Standards**: [development/TESTING_GUIDELINES.md](development/TESTING_GUIDELINES.md) - MANDATORY
- **Code Standards**: [development/DEVELOPMENT_STANDARDS.md](development/DEVELOPMENT_STANDARDS.md)
- **Setup Guides**: [development/DEVELOPMENT_SETUP_BACKEND.md](development/DEVELOPMENT_SETUP_BACKEND.md), [development/DEVELOPMENT_SETUP_FRONTEND.md](development/DEVELOPMENT_SETUP_FRONTEND.md)

## ✨ Phase 5: Complete Test Suite Migration - ✅ COMPLETE

**Phase 5 Final Completion** (December 13, 2025)

The entire test suite has been migrated to use the **RepositoryFactory pattern** with comprehensive pytest fixtures for dependency injection. This enables cleaner, more maintainable tests across all components.

### Phase 5 Documentation

| Phase | Status | Details |
|-------|--------|---------|
| **Phase 5A** | ✅ Complete | Foundation fixtures (20+ fixtures across hierarchy) |
| **Phase 5B** | ✅ Complete | Fixture consolidation (176 issues resolved) |
| **Phase 5C** | ✅ Complete | Backend API tests (67/73 passing, 92%) |
| **Phase 5D** | ✅ Complete | Performance tests (22/22 passing, 100%) |
| **Phase 5E** | ✅ Complete | Player component tests (54/54 passing, 100%) |
| **Phase 5F** | ✅ Complete | Final validation and documentation |

### Phase 5 Key Resources

- **[../PHASE_5_FINAL_COMPLETION_SUMMARY.md](../PHASE_5_FINAL_COMPLETION_SUMMARY.md)** - Comprehensive completion report with all architecture patterns
- **[../PHASE_5_OVERALL_COMPLETION.md](../PHASE_5_OVERALL_COMPLETION.md)** - Overall status summary of all 6 phases
- **[development/DEVELOPMENT_SETUP_BACKEND.md#testing-with-phase-5-fixtures-pytest](development/DEVELOPMENT_SETUP_BACKEND.md#testing-with-phase-5-fixtures-pytest)** - Complete pytest fixtures guide with examples
- **[development/DEVELOPMENT_SETUP_FRONTEND.md#phase-5-frontend--backend-test-integration](development/DEVELOPMENT_SETUP_FRONTEND.md#phase-5-frontend--backend-test-integration)** - Frontend & backend integration testing

### Fixture Architecture Highlights

**20+ Fixtures Organized in Hierarchy:**
- **Main Fixtures** - RepositoryFactory, LibraryManager, individual repositories
- **Backend Fixtures** - Mock factories for API endpoint testing
- **Player Fixtures** - 8 component fixtures for player testing
- **Performance Fixtures** - Dual-mode benchmarking and load testing

**Key Patterns:**
- ✅ Dependency Injection via callable pattern
- ✅ Parametrized dual-mode testing (automatic test multiplication)
- ✅ Fixture composition with clean hierarchy
- ✅ Automatic cleanup between tests
- ✅ Full backward compatibility with LibraryManager

## 📋 Documentation Organization

This documentation follows DRY principles:

- **Single Source of Truth** - Each topic stored in one logical location
- **Clear Hierarchy** - Organized by functionality and detail level
- **Cross-Referenced** - Links between related documents
- **Navigable** - README files guide discovery

---

**Version**: 1.1.0-beta.5 | **Last Updated**: November 30, 2024
