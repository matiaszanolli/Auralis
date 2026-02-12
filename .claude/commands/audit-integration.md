# Backend-Frontend-Engine Integration Audit

Trace the critical data flows between the Auralis audio engine, FastAPI backend, and React frontend. For each flow, verify that schemas match at every boundary, errors are handled on both sides, audio data is correctly transformed, and WebSocket messages are consistent. Then create GitHub issues for every new confirmed finding.

## Project Layout

All code lives in a single repo at `/mnt/data/src/matchering`:

- **Audio Engine**: `auralis/` — Core Python audio engine
- **Backend**: `auralis-web/backend/` — FastAPI REST + WebSocket (:8765)
- **Frontend**: `auralis-web/frontend/` — React 18, TypeScript, Vite, Redux
- **Rust DSP**: `vendor/auralis-dsp/` — PyO3 module
- **Tests**: `tests/` — 850+ tests across 21 directories

## Severity Definitions

| Severity | Definition | Examples |
|----------|-----------|---------|
| **CRITICAL** | Audio data loss or silent corruption across a boundary. | Dropped audio chunks, sample rate mismatch between engine and streaming, truncated playback |
| **HIGH** | Failures under realistic conditions at a boundary. | WebSocket message schema mismatch, timeout causing playback stutter, unhandled error propagation |
| **MEDIUM** | Inconsistencies with workarounds or that affect non-critical paths. | Different field names for same concept, inconsistent error codes, stale frontend state |
| **LOW** | Cosmetic or documentation gaps at boundaries. | Missing API schema docs, undocumented WebSocket message types, unused response fields |

## Flows to Trace

### Flow 1: Track Playback (Full Pipeline)
| Step | Layer | File |
|------|-------|------|
| User clicks play | Frontend | `src/hooks/player/` hooks, `src/store/` player slice |
| REST request | Frontend | `src/services/` API client |
| Play endpoint | Backend | `routers/player.py` or `routers/streaming.py` |
| Audio loading | Engine | `auralis/io/unified_loader.py` |
| Processing | Engine | `auralis/core/hybrid_processor.py` → `simple_mastering.py` |
| Chunking | Backend | `chunked_processor.py` (30s chunks, 3s crossfade) |
| WebSocket stream | Backend | `audio_stream_controller.py` |
| Audio playback | Frontend | WebSocket hook → Web Audio API |

**Check**: Sample rate consistency from file to playback. Chunk boundaries — do crossfades preserve continuity? WebSocket binary frame format — does the frontend decode it correctly? What happens when processing is slower than playback?

### Flow 2: Library Browsing
| Step | Layer | File |
|------|-------|------|
| User navigates | Frontend | `src/hooks/library/`, `src/store/` library slice |
| REST requests | Frontend | `src/services/` API client |
| Library endpoints | Backend | `routers/` (albums, artists, playlists, tracks) |
| Database queries | Engine | `auralis/library/manager.py` → `repositories/` |
| Response format | Backend | `schemas.py` |

**Check**: Pagination — consistent between frontend expectations and backend response? Field naming — camelCase (frontend) vs snake_case (backend)? Null handling — what happens when optional metadata is missing? Large libraries — does the frontend handle 100k+ tracks?

### Flow 3: Audio Enhancement
| Step | Layer | File |
|------|-------|------|
| User adjusts settings | Frontend | Enhancement hooks/components |
| Settings API call | Frontend | `src/services/` |
| Enhancement endpoint | Backend | `routers/enhancement.py` |
| Processing config | Engine | `auralis/core/config.py` |
| DSP pipeline | Engine | `auralis/core/hybrid_processor.py` → DSP modules |
| Real-time application | Engine | `auralis/player/realtime_processor.py` |

**Check**: Config format — do frontend slider values map correctly to engine parameters? Range validation — can the frontend send out-of-range values? Real-time vs offline — is the same config used for both paths? Latency — does enhancement cause audible gaps?

### Flow 4: Library Scanning
| Step | Layer | File |
|------|-------|------|
| User adds folder | Frontend | Library management hooks |
| Scan request | Backend | `routers/library.py` (or similar) |
| Filesystem scan | Engine | `auralis/library/scanner.py` |
| Metadata extraction | Engine | `auralis/io/unified_loader.py` |
| Database insert | Engine | `auralis/library/manager.py` → repositories |
| Progress updates | Backend | WebSocket or polling |
| UI update | Frontend | Redux store |

**Check**: Progress reporting — does the frontend receive scan progress? Error handling — what happens when a file can't be read? Duplicate detection — does rescan handle already-imported tracks? Large folders — timeout or chunking?

### Flow 5: WebSocket Lifecycle
| Step | Layer | File |
|------|-------|------|
| Connection init | Frontend | WebSocket hooks |
| WS accept | Backend | `audio_stream_controller.py` or `main.py` |
| Message routing | Backend | WebSocket handler |
| Binary audio frames | Backend | Chunk encoder |
| Frame decode | Frontend | WebSocket hook |

**Check**: Connection establishment — handshake protocol? Message types — are all types documented and handled on both sides? Binary vs text frames — consistent usage? Reconnection — does the frontend re-establish state after disconnect? Backpressure — what happens when the frontend can't consume frames fast enough?

### Flow 6: Fingerprint & Similarity
| Step | Layer | File |
|------|-------|------|
| Similarity request | Frontend | Fingerprint/similarity hooks |
| Similarity endpoint | Backend | `routers/similarity.py` |
| Fingerprint engine | Engine | `auralis/analysis/fingerprint/` |
| Database lookup | Engine | `auralis/library/repositories/` (fingerprint, similarity repos) |
| Results format | Backend | `schemas.py` |

**Check**: Fingerprint format — is it consistent between compute and lookup? Similarity scores — range and precision? Missing fingerprints — graceful fallback? Batch vs single — consistent API?

### Flow 7: Artwork
| Step | Layer | File |
|------|-------|------|
| Artwork request | Frontend | Image components, hooks |
| Artwork endpoint | Backend | `routers/artwork.py` |
| Artwork extraction | Engine | Metadata/artwork services |
| Image serving | Backend | Static file or stream response |

**Check**: Image formats — are all common formats handled? Cache headers — are they set correctly? Missing artwork — fallback behavior? Large images — resizing on backend or frontend?

## Per-Flow Verification Checklist

For EVERY flow, systematically check:
- [ ] **Schema match**: Request fields sent == fields expected. Response fields returned == fields consumed.
- [ ] **Error handling**: Does the frontend handle 4xx and 5xx responses gracefully?
- [ ] **Timeouts**: Frontend timeout vs backend processing time — compatible?
- [ ] **Data types**: Sample rates, bit depths, timestamps, durations — consistent units and precision?
- [ ] **Null handling**: What happens when optional fields are missing on either side?
- [ ] **Case conversion**: camelCase ↔ snake_case at the API boundary?

## Deduplication (MANDATORY)

Before reporting ANY finding:
1. Run: `gh issue list --limit 200 --json number,title,state,labels`
2. Search for keywords from your finding in existing issue titles
3. If OPEN: skip. If CLOSED + regressed: report as regression. If no match: NEW.

## Phase 1: Audit

Write your report to: **`docs/audits/AUDIT_INTEGRATION_<TODAY>.md`** (use today's date).

### Per-Finding Format
```
### <ID>: <Short Title>
- **Severity**: CRITICAL | HIGH | MEDIUM | LOW
- **Flow**: <which of the 7 flows>
- **Boundary**: <sender layer> → <receiver layer>
- **Location**: `<sender-file>:<line>` → `<receiver-file>:<line>`
- **Status**: NEW | Existing: #NNN | Regression of #NNN
- **Description**: What is wrong at this boundary
- **Evidence**: Code from both sides showing the mismatch
- **Impact**: What breaks and when
- **Suggested Fix**: Which side should change and how
```

## Phase 2: Publish to GitHub

For every finding with **Status: NEW** or **Regression**, create a GitHub issue:
- **Title**: `[<TODAY>] <SEVERITY> - <Short Title>`
- **Labels**: severity label + domain label(s) (`backend`, `frontend`, `audio-integrity`, `websocket`, `streaming`, `library`, `fingerprint`) + `bug`
- **Body**: Summary, Evidence from both sides, Impact, Related Issues, Proposed Fix, Acceptance Criteria, Test Plan
- **Cross-reference** related existing issues with `gh issue comment`.
- **Print summary table** at the end.
