---
description: "Unified severity scale and classification rules for all Auralis audit skills"
---

# Unified Severity Definitions — Auralis

This file is referenced by all audit skills. Do NOT use as a slash command (prefixed with `_`).

**Severity is about IMPACT, not likelihood.** A rare but catastrophic bug is CRITICAL, not MEDIUM.

## CRITICAL

Immediate, unrecoverable failure or data/audio corruption. No workaround.

- Sample-count mismatch in a public DSP stage (clicks/gaps on every playback)
- Buffer corruption from missing `audio.copy()` before in-place op
- Path traversal / arbitrary-file read in a backend route
- Database corruption from concurrent writes without locking
- In-place mutation of a NumPy array shared across threads/stages
- Exploitable security breach (auth bypass, RCE, SQL injection)
- Data loss (library DB corruption, lost user playlists)

## HIGH

Fails under realistic conditions (concurrency, large libraries, extended playback, edge-case files). Fix before next release.

- Phase cancellation in parallel/multi-band DSP
- Deadlock or lock-ordering violation in player or library
- RLock held across a callback (re-entrancy hazard)
- WebSocket chunk drops at 30 s boundaries
- Gapless transition with audible gap (>1 ms silence)
- Memory leak that compounds during playback
- Missing input validation on a public, network-exposed route
- N+1 query that scales with library size
- FFmpeg subprocess not terminated on cancellation (zombie process)

## MEDIUM

Incorrect behavior with workarounds, defense-in-depth gaps, or affects non-critical paths. Fix within 2 sprints.

- Inconsistent dtype handling across DSP stages (silent `float32 → float64`)
- Missing copy-before-modify in a non-critical path
- Fingerprint accuracy degradation at edge cases (silence, pure noise)
- Schema mismatch between backend response and frontend type
- Stale Redux state after a backend event
- Rate-limiting gap on non-sensitive routes
- Migration that lacks rollback / backup verification
- Repository-pattern violation (raw SQL outside `repositories/`)

## LOW

Code quality, maintainability, hardening opportunities. Fix opportunistically.

- Redundant array copies hurting performance (no correctness impact)
- Sub-optimal FFT windowing parameters
- Unused analysis metrics / dead code
- Component > 300 lines (violates project modularity rule)
- Deprecated API still imported but not breaking
- Missing type hints on internal functions
- Test coverage gaps (where code works correctly)
- Hard-coded constant that should be in `auralis/core/config.py`

## Special Rules

| Condition | Minimum Severity |
|-----------|-----------------|
| Sample-count mismatch in any DSP stage | CRITICAL |
| In-place mutation of caller-owned NumPy array | CRITICAL |
| NaN/Inf escapes a DSP stage into downstream audio | HIGH |
| `audio.copy()` missing before in-place op (any path) | HIGH |
| Repository-pattern violation (raw SQL) | MEDIUM |
| Lock held across a callback or `await` | HIGH |
| Missing `selectinload()` on a list endpoint | MEDIUM |
| Migration without backup or file-lock | HIGH |
| WebSocket handler not idempotent on reconnect | MEDIUM |
| Public route without input validation | HIGH |
| Path-traversal / SSRF / SQLi in any route | CRITICAL |
| FFmpeg subprocess can be orphaned | HIGH |
| Component > 300 lines | LOW |
| Frontend imports `tokens` is missing (raw hex colors) | LOW |
| Rust DSP returns wrong dtype/shape to PyO3 boundary | HIGH |
| Rust DSP holds GIL during long compute | MEDIUM |

## Decision Tree

```
Is it a security breach (auth bypass, RCE, path traversal, SQLi)?
  → YES: CRITICAL

Does it corrupt audio samples, DB state, or user files?
  → YES: CRITICAL (data integrity loss)

Does it cause audible artifacts (clicks, gaps, phase cancellation, dropped chunks)?
  → YES: At least HIGH

Does it affect concurrent access to shared state (audio buffer, player, DB, WS)?
  → YES: At least HIGH

Is there a missing input validation on a public, network-exposed surface?
  → YES: At least HIGH (CRITICAL if it leads to file/DB access)

Is there a resource leak that compounds (memory, file handles, subprocesses)?
  → YES: At least HIGH

Is there a schema/contract mismatch between backend and frontend?
  → YES: At least MEDIUM

Is it a repository-pattern violation, raw SQL, or N+1 query?
  → YES: At least MEDIUM

Is it a code-quality / maintainability / hardening issue only?
  → YES: LOW

Otherwise → MEDIUM
```

## Classification Rules

1. **Severity is about IMPACT, not likelihood.** A rare but catastrophic bug is CRITICAL, not MEDIUM.
2. **Downgrade if mitigated.** A missing validation on a route only accepting localhost connections is MEDIUM, not HIGH. (Auralis is desktop-only and binds to localhost; see CLAUDE.md.)
3. **Upgrade if chained.** Two MEDIUM findings that combine into audio corruption are HIGH or CRITICAL.
4. **Be consistent.** The same class of bug should get the same severity across all audit reports, regardless of which audit skill found it.
5. **Audio integrity elevates severity.** Any finding that can cause audible artifacts (clicks, gaps, phase issues) is at least HIGH.
