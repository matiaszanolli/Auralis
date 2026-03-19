# Unified Severity Definitions

This file is referenced by all audit skills. Do NOT use as a slash command (prefixed with `_`).

## Severity Scale

| Severity | Definition | Examples |
|----------|-----------|---------|
| **CRITICAL** | Happening NOW in production. Causes audio corruption, data loss, or exploitable security breach. No workaround. Requires immediate fix. | Sample count mismatch causing clicks, buffer corruption from missing copy, path traversal to arbitrary files, database corruption from concurrent writes |
| **HIGH** | Will cause failures under realistic conditions (concurrency, large libraries, extended playback, edge-case files). Fix before next release. | Phase cancellation in parallel DSP, RLock deadlock in player, WebSocket dropped chunks, gapless transition gap, memory leak during playback |
| **MEDIUM** | Incorrect behavior with workarounds, defense-in-depth gaps, or affects non-critical paths. Fix within 2 sprints. | Inconsistent dtype handling, missing input validation, stale frontend state, schema mismatch, rate limiting gaps |
| **LOW** | Code quality, maintainability, hardening opportunities, or minor inconsistencies. Fix opportunistically. | Redundant array copies, unused metrics, component > 300 lines, deprecated APIs not yet breaking, missing type hints |

## Classification Rules

1. **Severity is about IMPACT, not likelihood.** A rare but catastrophic bug is CRITICAL, not MEDIUM.
2. **Downgrade if mitigated.** A missing validation on a route that only accepts localhost connections is MEDIUM, not HIGH.
3. **Upgrade if chained.** Two MEDIUM findings that combine into audio corruption are HIGH or CRITICAL.
4. **Be consistent.** The same class of bug should get the same severity across all audit reports, regardless of which audit skill found it.
5. **Audio integrity elevates severity.** Any finding that can cause audible artifacts (clicks, gaps, phase issues) is at least HIGH.
