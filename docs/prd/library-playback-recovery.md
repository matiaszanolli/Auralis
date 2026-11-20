# Library and playback recovery — Product Requirements

**Status**: PROPOSED (2026-11-19). First draft from the v1.5.1 recovery scope.

**Scope**: Scan and browse a local library, retain its fingerprints across restart, and play its tracks in normal and enhanced modes. This is the second v1.5.1 recovery slice, covering REC-02 through REC-04.

**Related**: The recovery audit defines the working-state scenarios. The subsystem guides describe the library and playback paths under test.

| Mechanism | Owning reference |
|---|---|
| Scan, fingerprint, and persistence | [Fingerprinting guide](../subsystems/fingerprinting.md) |
| Playback, chunk processing, and WebSocket | [Data flow](../architecture/data-flow.md) · [WebSocket API](../../auralis-web/backend/WEBSOCKET_API.md) |
| Recovery scenarios and release validation | [Definition of working](../audits/AUDIT_RECOVERY_2026-07-24.md#definition-of-working) · [Release checklist](../releases/RELEASE_CHECKLIST_1_5_1.md) |

Requirement IDs use the `PLAY-` prefix. **MUST**, **SHOULD**, and **MAY** have their RFC 2119 meanings.

## 1. Product thesis

A listener should be able to open a new library, pick a track, and hear it with or without enhancement. Across scan, restart, and rapid selections, Auralis should preserve the library and play the track the listener most recently selected.

## 2. Terminology

| Term | Meaning |
|---|---|
| Fresh library | A database created during first startup against an empty home. |
| Migrated library | A database brought from an earlier schema through the supported migration path. |
| Last intent | The latest track selection in user action order. |
| PCM invariant | The stream exposes valid channels and finite float32 PCM and preserves the number of audio sample frames. |

## 3. Core model

The recovery scenario follows scan → persist → browse → select → stream → restart. Scoped regressions provide evidence at individual boundaries. The complete scenario exercises their interaction.

The snapshot below describes behavior at HEAD on 2026-11-19.

| Mechanism | Today |
|---|---|
| First fingerprint write | Regression coverage pins fresh-install insert defaults. Fresh and migrated schemas are compared by the schema parity test. [Fresh-install regression](../../tests/auralis/library/test_fingerprint_fresh_install_defaults_5530.py) · [Schema parity regression](../../tests/auralis/library/test_schema_parity_5753.py) |
| Column mono | Regressions pin per-channel loudness state and preservation of a one-channel input by the processor. [Loudness regression](../../tests/auralis/dsp/test_loudness_channel_counts_5550.py) · [Processor input regression](../../tests/auralis/core/test_hybrid_input_contract_6118.py) |
| Rapid track selection | The frontend regression for [#4426](https://github.com/matiaszanolli/Auralis/issues/4426) covers the late response from a superseded selection. [Selection regression](../../auralis-web/frontend/src/hooks/player/__tests__/usePlayTrack.test.ts) |
| Combined workflow | The release checklist still requires evidence from an isolated fresh-library run. [Required validation](../releases/RELEASE_CHECKLIST_1_5_1.md#required-validation) |

## 4. Goals and non-goals

### 4.1 Goals

- **PLAY-G-001.** A user can scan, browse, and reopen the fixture library across restart.
- **PLAY-G-002.** Each fixture plays in both modes with the PCM invariant intact and the most recently selected track active.

### 4.2 Non-goals

- **PLAY-NG-001.** Cache and similarity features and visual polish are outside the working-state slice. [Recovery scope](../MASTER_ROADMAP.md#4-active--near-term) |
- **PLAY-NG-002.** Broad suite cleanup belongs to the general maintenance backlog. The working-state checks cover the named user flows. [Definition of working](../audits/AUDIT_RECOVERY_2026-07-24.md#definition-of-working) |

## 5. Requirements by area

### 5.1 Library (`PLAY-LIB`)

- **PLAY-LIB-001.** A fresh or migrated library MUST reload the fingerprints persisted before restart.
- **PLAY-LIB-002.** Library browsing MUST return the expected totals, page contents, album and artist drill-downs, and artwork for the fixture library.

### 5.2 Player (`PLAY-CTRL`)

- **PLAY-CTRL-001.** Normal and enhanced playback MUST support seek, pause, resume, next, previous, and queue updates on the fixture tracks.
- **PLAY-CTRL-002.** The last selection MUST remain active when responses to two rapid track selections arrive in reverse order.

### 5.3 Stream and session (`PLAY-PCM`)

- **PLAY-PCM-001.** Normal and enhanced playback MUST emit the expected sample frame count for each fixture, including one-dimensional and `(samples, 1)` mono inputs at the audio boundary.
- **PLAY-PCM-002.** Normal and enhanced playback MUST emit finite float32 PCM.
- **PLAY-PCM-003.** Normal and enhanced playback MUST emit PCM with the channel count advertised by the stream.
- **PLAY-PCM-004.** A healthy playback session MUST keep its WebSocket open through the heartbeat interval defined in the recovery audit.
- **PLAY-PCM-005.** The playback scenario MUST complete without uncaught browser or Electron exceptions or unhandled promise rejections.

## 6. Deliberate deviations and risks

| Change or risk | User impact | Requirement or mitigation |
|---|---|---|
| Fresh and migrated schemas can differ. | Returning users and first-time users can see different persistence failures. | `PLAY-LIB-001`, verify both database histories. |
| Linux, Windows, and macOS use packaged playback dependencies. | Source-run success provides incomplete evidence for installed users. | Repeat the working-state smoke for the required [release artifacts](../releases/RELEASE_CHECKLIST_1_5_1.md#artifact-validation). |
| Component tests cover individual boundaries. | A regression in the combined flow can evade the component suites. | Run the isolated workflow and repeat it at the release checklist threshold. |

## 7. Scope by surface and acceptance

### 7.1 Scope by surface

| Surface | Scope | Reason |
|---|---|---|
| Fresh and migrated SQLite | In scope | Both schema histories must preserve fingerprints. |
| Stereo WAV, mono WAV, FFmpeg-routed MP3 | In scope | The recovery fixture covers both channel shapes and the FFmpeg decode path. |
| Normal and enhanced browser/Electron playback | In scope | Both paths must preserve frames and obey track selections. |
| Cache, similarity, and visual polish | Outside initial release scope | Follow-up work is ordered in the roadmap. |

### 7.2 Acceptance

| Scenario | Fixture and steps | Pass condition | Requirements |
|---|---|---|---|
| Scan, browse, and restart | In temporary homes, scan the WAV/MP3 fixture and enough synthetic catalog entries for three pages. Repeat the persistence check with a migrated database. | Totals, page contents, artwork, and drill-downs match the fixture. The same fingerprints reload after restart. | `PLAY-LIB-001`, `PLAY-LIB-002` |
| Play in both modes | Play fixture tracks and exercise the transport and queue controls. Check mono at the audio boundary in vector and column form. | The controls have the expected effects. PCM is finite float32, its frame count matches the source at the stream sample rate, and its channel count matches the metadata. | `PLAY-CTRL-001`, `PLAY-PCM-001`, `PLAY-PCM-002`, `PLAY-PCM-003` |
| Latest selection and steady connection | Select two fixture tracks quickly with the first request delayed. Keep the healthy session open for the audit's heartbeat duration and capture renderer errors. | The second track remains active, no heartbeat reconnect occurs, and no uncaught renderer error is recorded. | `PLAY-CTRL-002`, `PLAY-PCM-004`, `PLAY-PCM-005` |

## 8. Metrics

| Metric | Definition and granularity | Results recorded in |
|---|---|---|
| Working-state coverage | Passing checks divided by the applicable checks in the recovery audit, per test environment. | [Release checklist](../releases/RELEASE_CHECKLIST_1_5_1.md#required-validation) |
| Consecutive clean runs | Uninterrupted count of passing fast-gate runs and, separately, complete end-to-end runs. | [Release checklist](../releases/RELEASE_CHECKLIST_1_5_1.md#required-validation) |

## 9. Delivery sequence

**Phase 0 — Baseline the existing fixes.** Map the July findings and later scoped regressions to the acceptance scenarios. Exit: each scenario has a fixture, a pass rule, and a gap recorded where full-flow evidence is missing.

**Phase 1 — Verify the working-state slice.** Use the isolated launch path from [application startup](application-startup.md) to cover the library, player, and stream requirements. Exit: the audit's definition of working passes against a fresh temporary home, with the migrated-library result recorded alongside it.

**Phase 2 — Verify repeatability.** Run the fast gate and repeated end-to-end workflow defined in the checklist. Exit: both run counts meet the checklist thresholds with zero failures in the successful sequences.

## 10. Decisions required

No decisions required. The recovery audit and release checklist define the initial validation scope.

## 11. Document map

| Need | Reference |
|---|---|
| Startup dependency | [Application startup](application-startup.md) |
| Working-state criteria and recovery sequence | [Recovery audit](../audits/AUDIT_RECOVERY_2026-07-24.md#recovery-plan) |
| Milestone order | [Master roadmap](../MASTER_ROADMAP.md#4-active--near-term) |
| Release evidence | [Release checklist](../releases/RELEASE_CHECKLIST_1_5_1.md) |

## 12. Revision and review log

| Rev | Date | Change | Review |
|---|---|---|---|
| 1 | 2026-11-19 | Drafted from the recovery scope and linked the scoped regressions that followed the audit. | — |
