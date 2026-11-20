# Application startup — Product Requirements

**Status**: PROPOSED (2026-11-20). Source implementation and web startup smoke are in place. Installed release candidates still need validation.

**Scope**: Startup, readiness, failure reporting, and shutdown for source-run web, Electron development, and packaged Electron. This is the first v1.5.1 recovery slice, covering REC-01 and REC-05.

**Related**: The recovery audit defines the launch contract and the release checklist records proof.

| Mechanism | Owning reference |
|---|---|
| Process ownership, startup modes, and port propagation | [Recovery audit startup plan](../audits/AUDIT_RECOVERY_2026-07-24.md#phase-0--make-startup-truthful-and-single-owner) |
| Backend health and initialized components | [Backend API guide](../subsystems/backend-api.md) |
| Release validation | [v1.5.1 release checklist](../releases/RELEASE_CHECKLIST_1_5_1.md) |

Requirement IDs use the `BOOT-` prefix. **MUST**, **SHOULD**, and **MAY** have their RFC 2119 meanings.

## 1. Product thesis

Developers need a command that launches a usable application and gives a clear failure when startup breaks. Packaged users need the same assurance from the desktop app. A launch is successful once the initialized backend can serve the selected mode.

## 2. Terminology

| Term | Meaning |
|---|---|
| Process owner | The supervisor responsible for starting and stopping a child process it created for a launch. |
| Liveness | The backend process is responsive to an HTTP request. |
| Readiness | The engine and library database are initialized and usable. |

## 3. Core model

A launch starts in **starting**, moves to **ready** after the backend readiness check, or reaches **failed** if a required child fails. On **stopping**, the owner shuts down its children.

The snapshot below describes behavior at HEAD on 2026-11-20.

| Mechanism | Today |
|---|---|
| Source web and Electron development | The root launcher starts the backend and Vite. Electron development opens the supervised Vite frontend. [Source launcher](../../launch-auralis-web.py) · [Desktop launcher](../../desktop/main.js) |
| Packaged Electron | Electron starts the bundled backend on its configured port and loads the bundled frontend. [Desktop launcher](../../desktop/main.js) |
| Backend readiness | `/api/ready` returns 503 when the library, player state manager, or fingerprint engine is unavailable. Supervisors check the launch ID to associate the response with their own backend. [Health contract regression](../../tests/backend/test_health_readiness_4684.py) |
| Integration isolation | A collected smoke test uses a temporary home and database and ephemeral backend and frontend ports. [Subprocess smoke](../../tests/integration/test_application_startup.py) |

## 4. Goals and non-goals

### 4.1 Goals

- **BOOT-G-001.** Each supported launch mode reaches readiness through its documented entry point.
- **BOOT-G-002.** Launch failures and shutdown leave the run's required child processes stopped.

### 4.2 Non-goals

- **BOOT-NG-001.** The library, playback, and repeated-session scenarios belong to [library and playback recovery](library-playback-recovery.md).
- **BOOT-NG-002.** Signing and installer distribution belong to the [release checklist](../releases/RELEASE_CHECKLIST_1_5_1.md#artifact-validation).

## 5. Requirements by area

### 5.1 Launch (`BOOT-RUN`)

- **BOOT-RUN-001.** The setup guide MUST identify the launch entry point for each supported mode.
- **BOOT-RUN-002.** The launch entry point MUST start without installing dependencies at runtime.
- **BOOT-RUN-003.** Each launch MUST have exactly one owner for its backend process.
- **BOOT-RUN-004.** Each launch MUST use the same effective backend port for the backend, its readiness probe, and the client connection.
- **BOOT-RUN-005.** The launcher MUST terminate with a failure result when a required child fails during startup.

### 5.2 Readiness (`BOOT-RDY`)

- **BOOT-RDY-001.** `/api/ready` MUST report success only when the engine and library database are initialized.
- **BOOT-RDY-002.** The launcher MUST signal startup success only after readiness succeeds.

### 5.3 Shutdown and verification (`BOOT-STOP`)

- **BOOT-STOP-001.** Shutdown MUST leave no child process created by the run alive.
- **BOOT-STOP-002.** Launch failure and shutdown MUST leave unrelated processes running.
- **BOOT-STOP-003.** The collected subprocess smoke test MUST use a temporary home and database.
- **BOOT-STOP-004.** The collected subprocess smoke test MUST use an ephemeral port.

## 6. Deliberate deviations and risks

| Change or risk | User impact | Requirement or mitigation |
|---|---|---|
| Readiness becomes the launch success signal. | A responsive server with a failed engine can otherwise present an unusable app. | `BOOT-RDY-001`, `BOOT-RDY-002` |
| A port may already be occupied. | Killing that listener could interrupt unrelated work. | `BOOT-STOP-002` |
| Launch tests can use a developer's persistent data. | The smoke could migrate or otherwise change a real library. | `BOOT-STOP-003` |

## 7. Scope by surface and acceptance

### 7.1 Scope by surface

| Surface | Scope | Reason |
|---|---|---|
| Source-run web | In scope | A clean checkout needs a supported launch path. |
| Electron development | In scope | Launch ownership and renderer connectivity need explicit verification. |
| Packaged Electron | In scope | Installed release candidates need readiness and shutdown checks. |

### 7.2 Acceptance

| Scenario | Fixture and steps | Pass condition | Requirements |
|---|---|---|---|
| Clean startup and exit | On a prepared checkout, run the documented source entry points with a temporary home and an available port. Record child commands and PIDs, readiness, and shutdown. | One backend is supervised, the client connects to its port, readiness precedes the success signal, no dependency installer runs, and all owned children exit. | `BOOT-RUN-001`, `BOOT-RUN-002`, `BOOT-RUN-003`, `BOOT-RUN-004`, `BOOT-RDY-001`, `BOOT-RDY-002`, `BOOT-STOP-001` |
| Failed startup | Through the collected smoke, inject a required-child failure and a backend initialization failure in separate runs with a temporary home and database and an ephemeral port. | A failure result is visible, startup success is absent, and owned children exit. | `BOOT-RUN-005`, `BOOT-RDY-001`, `BOOT-RDY-002`, `BOOT-STOP-001`, `BOOT-STOP-003`, `BOOT-STOP-004` |
| Port collision | Hold the selected port with an unrelated listener, then invoke the launcher. | The launch reports failure and the listener remains reachable. | `BOOT-RUN-005`, `BOOT-STOP-002` |
| Installed launch | Run the clean startup and exit scenario on the release candidates in the artifact checklist using a test profile. | Each candidate reaches readiness and leaves no child processes of the run behind. | `BOOT-RDY-002`, `BOOT-STOP-001` |

## 8. Metrics

| Metric | Definition and granularity | Results recorded in |
|---|---|---|
| Startup acceptance coverage | Passing scenarios divided by applicable scenarios, per mode and release artifact. | [Release checklist](../releases/RELEASE_CHECKLIST_1_5_1.md) |
| Leaked child processes | Owned child processes still alive after exit, per success and failure scenario. | [Release checklist](../releases/RELEASE_CHECKLIST_1_5_1.md#working-state-blockers) |

## 9. Delivery sequence

**Phase 0 — Baseline.** Identify the entry point, owner, and port for each mode and record where the current success and failure paths diverge. Exit: the evidence covers every mode in §7.1.

**Phase 1 — Source launch and readiness.** Cover `BOOT-RUN`, `BOOT-RDY`, and `BOOT-STOP` through the collected subprocess smoke. Exit: the source scenarios in §7.2 pass and the startup evidence is recorded in the release checklist. This supplies the launch path for [library and playback recovery](library-playback-recovery.md).

**Phase 2 — Installed verification.** Apply the installed-launch scenario to the release candidates. Exit: the checklist records a passing launch and shutdown for every required platform artifact.

## 10. Decisions required

No decisions required. The recovery plan supplies the ownership and readiness contract.

## 11. Document map

| Need | Reference |
|---|---|
| Milestone order | [Master roadmap](../MASTER_ROADMAP.md#4-active--near-term) |
| Launcher scope and original evidence | [Working-state recovery audit](../audits/AUDIT_RECOVERY_2026-07-24.md) |
| Required release evidence | [Release checklist](../releases/RELEASE_CHECKLIST_1_5_1.md) |

## 12. Revision and review log

| Rev | Date | Change | Review |
|---|---|---|---|
| 1 | 2026-11-19 | Drafted from the recovery scope and checked the startup baseline against the current tree. | — |
| 2 | 2026-11-20 | Added the source supervisor, backend readiness route, packaged Electron supervision, and isolated source smoke. | — |
