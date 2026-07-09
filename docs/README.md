# Auralis Documentation Hub

**Welcome to the Auralis development documentation.**

This is the central navigation point for all project documentation. Current project version: **1.2.1-beta.2** (see `auralis/version.py`, the source of truth)

---

## 🚀 Quick Start

**New to Auralis?** Start here:

1. **[Getting Started Guide](getting-started/)** - Installation and initial setup (5 minutes)
2. **[Development Setup](development/DEVELOPMENT_SETUP_BACKEND.md)** - Set up your development environment
3. **[CLAUDE.md](../CLAUDE.md)** - Complete technical reference (the authoritative guide)

---

## 📚 Documentation by Category

### 🏗️ Architecture & Design

- **[System Architecture](../CLAUDE.md)** - Overall system design (see CLAUDE.md)
- **[Audio Processing Pipeline](../CLAUDE.md)** - How audio flows through the system
- **[Frontend Architecture](frontend/)** - React/Redux structure and organization
- **[Database Design](../CLAUDE.md)** - SQLite schema and data models
- **[WebSocket Protocol](../CLAUDE.md)** - Real-time communication

### ⚡ Features

- **[Audio Enhancement](features/adaptive-mastering/)** - Mastering algorithms and presets
- **[Fingerprinting](features/)** - 25D fingerprinting and similarity search
- **[Player System](features/player/)** - Playback engine and queue
- **[Caching](features/cache-system/)** - Query and chunk caching
- **[Backend API](features/backend-api/)** - REST API enhancements

### 👨‍💻 Development

- **[TESTING_GUIDELINES.md](development/TESTING_GUIDELINES.md)** - Test quality standards (MANDATORY)
- **[DEVELOPMENT_SETUP_BACKEND.md](development/DEVELOPMENT_SETUP_BACKEND.md)** - Backend environment setup
- **[DEVELOPMENT_SETUP_FRONTEND.md](development/DEVELOPMENT_SETUP_FRONTEND.md)** - Frontend environment setup
- **[DEVELOPMENT_STANDARDS.md](development/DEVELOPMENT_STANDARDS.md)** - Coding standards (Python & TypeScript)
- **[Phase 5 Fixtures Guide](development/DEVELOPMENT_SETUP_BACKEND.md#testing-with-phase-5-fixtures-pytest)** - Pytest fixtures & dependency injection

### 📦 Deployment

- **[Releases](releases/)** - Release notes and binary packages
- **[User Guide](getting-started/BETA_USER_GUIDE.md)** - User documentation

---

## 🎯 Key Resources

| Resource | Purpose |
|----------|---------|
| **[../CLAUDE.md](../CLAUDE.md)** | ⭐ Complete technical reference (the authoritative guide) |
| **[MASTER_ROADMAP.md](MASTER_ROADMAP.md)** | Project roadmap and phases |
| **[development/TESTING_GUIDELINES.md](development/TESTING_GUIDELINES.md)** | Test quality standards (MANDATORY READ) |
| **[development/DEVELOPMENT_STANDARDS.md](development/DEVELOPMENT_STANDARDS.md)** | Coding standards |
| **[phases/completed/](phases/completed/)** | Phase completion summaries |

---

## 🔍 Finding Documentation

### By Topic
- **Audio Processing** → [CLAUDE.md Features](../CLAUDE.md#audio-processing)
- **Frontend/React** → [frontend/](frontend/) or [CLAUDE.md Frontend](../CLAUDE.md#frontend)
- **Backend/API** → [CLAUDE.md Backend Architecture](../CLAUDE.md#backend-architecture)
- **Database** → [CLAUDE.md Database](../CLAUDE.md#database)
- **Testing** → [development/TESTING_GUIDELINES.md](development/TESTING_GUIDELINES.md)
- **Performance** → [MASTER_ROADMAP.md](MASTER_ROADMAP.md)

### By Phase
- **Completed phases** → [phases/completed/](phases/completed/)
- **All Phases** → [MASTER_ROADMAP.md](MASTER_ROADMAP.md) (itself stale as of 2026-07-08 — see note below)
- ~~Historical → archive/~~ (this directory does not currently exist in the repo)

---

## 📋 Documentation Principles

This documentation is organized for **clarity and discovery**:

- **Single Source of Truth** - CLAUDE.md is authoritative for architecture
- **Organized by Topic** - Not by phase or date
- **Clear Hierarchy** - Browse by category or search by keyword
- **Always Current** - Aspirational; see the 2026-07-08 note at the bottom of this file for known drift
- **Archived, Not Deleted** - Historical docs in archive/ (reference only)

---

## ⚠️ Important Notes

1. **CLAUDE.md is authoritative** - For architecture decisions and technical details
2. **Archive is read-only** - Contains historical docs, don't reference in active code
3. **No duplicate documentation** - Each topic documented once
4. **Test guidelines are mandatory** - See [TESTING_GUIDELINES.md](development/TESTING_GUIDELINES.md)

---

**Current Version**: 1.2.1-beta.2 | **Last Updated**: July 8, 2026

> **Freshness note (2026-07-08)**: A broad docs/ audit this date found ~100 stale claims across ~60 files in this tree (wrong versions, broken links, removed/renamed code paths, outdated architecture descriptions). The highest-severity ones are fixed as of this note; the rest are tracked as GitHub issues (search for the `docs-audit-2026-07` label). When in doubt, verify against the actual code rather than trusting a doc's own "current" framing.
