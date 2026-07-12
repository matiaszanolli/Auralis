# Auralis Documentation

**Auralis** is a music player with real-time audio enhancement, shipped as an Electron desktop
app. Product version is the source of truth in [`auralis/version.py`](../auralis/version.py).

This is the developer documentation hub. It is organized around a small, **maintained** set of
architecture and subsystem docs — point-in-time history (phases, sessions, audits, fixes) lives
in [`archive/`](archive/) and is **not** current reference.

---

## Start here

| If you want to… | Read |
|-----------------|------|
| Understand the system at a glance | [architecture/overview.md](architecture/overview.md) |
| See how a play request flows end to end | [architecture/data-flow.md](architecture/data-flow.md) |
| Find where code lives on disk | [architecture/module-map.md](architecture/module-map.md) |
| Set up your environment and ship a change | [CONTRIBUTING.md](CONTRIBUTING.md) |

---

## Architecture

The spine of the developer docs — read these first.

- **[Overview](architecture/overview.md)** — the four layers, what makes Auralis distinctive,
  project-wide invariants, and the source-of-truth registry.
- **[Data Flow](architecture/data-flow.md)** — enhanced playback, library scan/fingerprinting,
  and REST browse, traced end to end with file references.
- **[Module Map](architecture/module-map.md)** — the file-level layout of every layer.

---

## Subsystem deep-dives

Authoritative, code-verified guides to the major subsystems. Each ends with a "where to start
reading" list.

| Subsystem | What it covers |
|-----------|----------------|
| **[DSP / Audio Engine](subsystems/dsp-engine.md)** | HybridProcessor, mode processors, SimpleMastering, DSP primitives, Rust DSP, chunked streaming, the audio invariants |
| **[Fingerprinting & Analysis](subsystems/fingerprinting.md)** | The 25 dimensions, extraction, `.25d` storage, similarity search, background scheduling, quality/genre |
| **[Backend API & WebSocket](subsystems/backend-api.md)** | App assembly, middleware, routers, the WS protocol, chunk orchestration, schemas, concurrency |
| **[Frontend](subsystems/frontend.md)** | App shell, Redux state, hooks, API/WS clients, design system, the Web Audio playback pipeline |

> More subsystems (player, library/repositories, I/O, services, learning) are documented inline
> in the code and summarized in the [module map](architecture/module-map.md). Deep-dives for
> them are the natural next expansion of this set.

---

## Development reference

Focused guides that back up [CONTRIBUTING.md](CONTRIBUTING.md):

- [development/DEVELOPMENT_SETUP_BACKEND.md](development/DEVELOPMENT_SETUP_BACKEND.md) —
  backend environment
- [development/DEVELOPMENT_SETUP_FRONTEND.md](development/DEVELOPMENT_SETUP_FRONTEND.md) —
  frontend environment
- [development/DEVELOPMENT_STANDARDS.md](development/DEVELOPMENT_STANDARDS.md) — coding
  standards (Python & TypeScript)
- [development/TESTING_GUIDELINES.md](development/TESTING_GUIDELINES.md) — test quality
  standards (**mandatory**)
- [development/TEST_EXECUTION_GUIDE.md](development/TEST_EXECUTION_GUIDE.md) — running the
  suites
- [development/REPOSITORY_PATTERN.md](development/REPOSITORY_PATTERN.md) — the DB access
  pattern
- [development/API_DESIGN_GUIDELINES.md](development/API_DESIGN_GUIDELINES.md) — REST/API
  conventions

Protocol & feature references:

- [../auralis-web/backend/WEBSOCKET_API.md](../auralis-web/backend/WEBSOCKET_API.md) — WS
  message reference *(note: stale on chunk size — trust `chunk_boundaries.py`)*
- [guides/](guides/) — feature-level design notes and integration guides *(mixed freshness)*
- [features/](features/) — per-feature documentation

---

## Also at the repo root

- [../README.md](../README.md) — user-facing project readme and downloads
- [../CLAUDE.md](../CLAUDE.md) — condensed technical reference and codebase map
- [../ARCHITECTURE.md](../ARCHITECTURE.md) — processor-hierarchy summary
- [../FIRST_TIME_SETUP.md](../FIRST_TIME_SETUP.md) — end-user setup

---

## Archive

[`archive/`](archive/) holds ~300 historical documents (phases, sessions, completed audits,
fixes, refactoring reports). **Reference only — do not treat any of it as current.** See
[archive/README.md](archive/README.md).

---

## Conventions for these docs

- **Evergreen, not dated.** Living docs describe how the code works *now*. Point-in-time
  write-ups go in `archive/`.
- **Cite the code.** Link to `path:line` so claims are checkable and drift is visible.
- **When docs and code disagree, code wins** — see the source-of-truth registry in
  [architecture/overview.md](architecture/overview.md#source-of-truth-registry).
