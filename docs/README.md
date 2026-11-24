# Auralis Documentation

**Auralis** is a local music player with real-time automatic mastering, shipped as an Electron
desktop app. The product version's source of truth is [`auralis/version.py`](../auralis/version.py).

This hub indexes the **maintained** documentation: architecture, subsystem deep-dives, and
development, release and user guides. Everything listed here describes the code as it is now.
Point-in-time material (plans, analyses, fix write-ups, superseded guides) lives in
[`archive/`](archive/) and is not current reference.

---

## Start here

| If you want to… | Read |
|-----------------|------|
| Use the app | [User guide](getting-started/USER_GUIDE.md) |
| Set up a development environment | [FIRST_TIME_SETUP.md](../FIRST_TIME_SETUP.md) |
| Ship a change | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Understand the system at a glance | [architecture/overview.md](architecture/overview.md) |
| Follow a play request end to end | [architecture/data-flow.md](architecture/data-flow.md) |
| Find where code lives | [architecture/module-map.md](architecture/module-map.md) |
| Know what blocks the v1.5.1 release | [release checklist](releases/RELEASE_CHECKLIST_1_5_1.md) · [release notes](releases/RELEASE_NOTES_1_5_1.md) |
| See what is planned | [MASTER_ROADMAP.md](MASTER_ROADMAP.md) · [product requirements](prd/README.md) |

---

## Architecture

- **[Overview](architecture/overview.md):** the four layers, the design rules (analysis is
  whole-track, rendering is per chunk), project-wide invariants, and the source-of-truth registry.
- **[Data flow](architecture/data-flow.md):** enhanced and normal playback, library scan and
  fingerprinting, and REST browse, traced through the code.
- **[Module map](architecture/module-map.md):** the file-level layout of every layer.
- **[ARCHITECTURE.md](../ARCHITECTURE.md):** naming and service conventions (Processor, Service,
  Manager, Repository, Factory, Worker), dependency injection, and the coordinator-plus-mixin split.

## Subsystem deep-dives

Each one ends with a "where to start reading" list.

| Subsystem | What it covers |
|-----------|----------------|
| **[DSP engine](subsystems/dsp-engine.md)** | `HybridProcessor` and its `process()` contract, the track-level mastering plan, the mode processors, DSP stages, the offline SimpleMastering CLI, and the audio invariants |
| **[Fingerprinting](subsystems/fingerprinting.md)** | The 25 dimensions, whole-track extraction in Rust, `.25d` sidecars, the two fingerprint queues, similarity and the K-NN graph, quality and genre analysis |
| **[Player](subsystems/player.md)** | The Python playback engine, its state model and locking, the queue and gapless engine, and how the backend's `PlayerState` relates to it |
| **[Library](subsystems/library.md)** | `LibraryDatabase`, the models, the 12 repositories and their eager-loading rules, migrations, and the scanner |
| **[Backend API](subsystems/backend-api.md)** | App startup, middleware, the 20 routers, chunk orchestration, processor leases, executors, and errors |
| **[Frontend](subsystems/frontend.md)** | Providers and app shell, Redux slices, hooks, REST and WebSocket clients, design system, and the Web Audio playback pipeline |

## Protocols and features

- [WebSocket protocol](../auralis-web/backend/WEBSOCKET_API.md): every message type in both
  directions, plus heartbeats, rate limits and error codes.
- [Backend configuration](../auralis-web/backend/CONFIG.md): every environment variable the
  backend reads.
- [Chunk and cache architecture](features/cache-system/CHUNK_AND_CACHE_ARCHITECTURE.md): chunk
  geometry, cache keys, invalidation and the reaper.
- [Artwork](features/ARTWORK.md): album covers and artist images.
- [Rust DSP crate](features/RUST_DSP_STATUS.md): what `vendor/auralis-dsp` exposes and how it is
  built.
- [Security model](security/SECURITY_MODEL.md): the threat model and every defense of the
  local API.

## Frontend

- [Frontend docs index](frontend/README.md)
- [UI style guide](UI_STYLE_GUIDE.md): the visual language, matched to the design tokens.
- [Player and enhancement pane](frontend/PLAYER_ENHANCEMENT_ARCHITECTURE.md)
- [Frontend testing commands](frontend/testing/TESTING_COMMANDS.md)

## Development

| Guide | Covers |
|-------|--------|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Ground rules, branches and commits, testing, CI gates, pull requests |
| [DEVELOPMENT_SETUP_BACKEND.md](development/DEVELOPMENT_SETUP_BACKEND.md) | Running the backend alone, env vars, debugging, tooling |
| [DEVELOPMENT_SETUP_FRONTEND.md](development/DEVELOPMENT_SETUP_FRONTEND.md) | Running the renderer, debugging, type checks, Vitest |
| [DEVELOPMENT_STANDARDS.md](development/DEVELOPMENT_STANDARDS.md) | Every enforced rule and the CI gate behind it |
| [TESTING_GUIDELINES.md](development/TESTING_GUIDELINES.md) | How to write tests (**mandatory**) |
| [TEST_EXECUTION_GUIDE.md](development/TEST_EXECUTION_GUIDE.md) | How to run tests, markers, what CI runs, the failure baselines |
| [REPOSITORY_PATTERN.md](development/REPOSITORY_PATTERN.md) | How to add or change a repository |
| [API_DESIGN_GUIDELINES.md](development/API_DESIGN_GUIDELINES.md) | REST conventions the routers follow |
| [BUILD_QUICK_REFERENCE.md](development/BUILD_QUICK_REFERENCE.md) | Packaging and the release pipeline |
| [STREAMLINING_PLAN.md](development/STREAMLINING_PLAN.md) | Retiring duplicate implementations, and the variation that is intentional |

## Releases and planning

- [MASTER_ROADMAP.md](MASTER_ROADMAP.md): current state, what shipped, and the open backlog by theme.
- [releases/CHANGELOG.md](releases/CHANGELOG.md): the project history.
- [releases/RELEASE_GUIDE.md](releases/RELEASE_GUIDE.md) and
  [releases/VERSIONING_STRATEGY.md](releases/VERSIONING_STRATEGY.md): how releases are cut and
  versioned.
- [prd/](prd/README.md): product requirements for milestones and workflow changes.
- [audits/](audits/): dated audit reports. The `/audit-*` commands write them, and
  [AUDIT_RECOVERY_2026-07-24.md](audits/AUDIT_RECOVERY_2026-07-24.md) defines the v1.5.1
  recovery scope.

The source tree identifies as **v1.5.1**, an unreleased recovery milestone; no v1.5.1 tag or
binaries exist. The latest tagged source version is `v1.2.1-beta.1`, and the latest release with
binaries is `v1.2.0-beta.2`.

## Also at the repo root

- [README.md](../README.md): the project overview, status and downloads.
- [CLAUDE.md](../CLAUDE.md): the condensed technical reference for contributors and coding
  agents (commands, codebase map, invariants, CI gates). [AGENTS.md](../AGENTS.md) points to it.

## Archive

[`archive/`](archive/) holds about 400 historical documents. They are reference only; see
[archive/README.md](archive/README.md).

---

## Conventions for these docs

- **Evergreen.** Living docs describe the code as it is now, in the present tense, with no
  "last updated" banners or history narration. Git carries the history. Point-in-time
  write-ups go in `archive/`.
- **Cite symbols, not line numbers.** Write `<path>.py::<Symbol>`. Line anchors rot on the
  next edit, and the path-reference gate rejects them.
- **Name deleted code in italics.** A backticked path must exist; the gate checks it.
- **One owner per fact.** Link to the doc that owns a fact instead of restating it.
- **When docs and code disagree, the code wins.** See the source-of-truth registry in
  [architecture/overview.md](architecture/overview.md#source-of-truth-registry).

The path-reference gate (`.claude/commands/_audit-validate.sh`, run by `path-references.yml`)
enforces the path, anchor and link rules on every living doc.
