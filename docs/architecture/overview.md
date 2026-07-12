# Architecture Overview

Auralis is a **music player with real-time audio enhancement**, shipped as a single
**Electron desktop application**. Everything runs on `localhost`: there is no server
deployment, no multi-user scenario, and no remote/LAN surface — a fact that shapes many
design decisions (no TLS, hardcoded `127.0.0.1:8765`, file-based locking, `file://` origins).

> **New here?** Read this page, then [data-flow.md](data-flow.md) to see how a play request
> travels end to end, then [module-map.md](module-map.md) for the file-level layout. For deep
> dives, see the [subsystem docs](../subsystems/).

---

## The four layers

```
┌─────────────────────────────────────────────────────────────────────┐
│  Electron shell (desktop/)                                           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  React frontend  (auralis-web/frontend/)                       │  │
│  │  React 18 · Redux · Vite · Web Audio API playback             │  │
│  └───────────────┬───────────────────────────┬───────────────────┘  │
│         REST (HTTP)                    WebSocket (/ws)                │
│  ┌───────────────▼───────────────────────────▼───────────────────┐  │
│  │  FastAPI backend  (auralis-web/backend/)  :8765               │  │
│  │  19 routers · WebSocket streaming · chunked processing        │  │
│  └───────┬───────────────────────┬───────────────────┬───────────┘  │
│  ┌───────▼──────────┐  ┌─────────▼─────────┐  ┌───────▼───────────┐  │
│  │ Audio engine     │  │ Library (SQLite)  │  │ Analysis /         │  │
│  │ auralis/core     │  │ auralis/library   │  │ fingerprinting     │  │
│  │ auralis/dsp      │  │ ~/.auralis/*.db   │  │ auralis/analysis   │  │
│  └───────┬──────────┘  └───────────────────┘  └───────┬───────────┘  │
│  ┌───────▼─────────────────────────────────────────────▼──────────┐  │
│  │  Rust DSP  (vendor/auralis-dsp/)  — PyO3 + gRPC fingerprint svc │  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

| Layer | Path | Language | Responsibility |
|-------|------|----------|----------------|
| **Frontend** | [`auralis-web/frontend/`](../../auralis-web/frontend/) | TypeScript / React | UI, Redux state, browser audio playback |
| **Backend** | [`auralis-web/backend/`](../../auralis-web/backend/) | Python / FastAPI | REST + WebSocket, chunk orchestration |
| **Core engine** | [`auralis/`](../../auralis/) | Python | DSP, analysis, library, player |
| **Rust DSP** | [`vendor/auralis-dsp/`](../../vendor/auralis-dsp/) | Rust / PyO3 | HPSS, YIN, Chroma, 25D fingerprint |

The **desktop wrapper** ([`desktop/`](../../desktop/)) is an Electron shell that bundles all of
the above and launches them together.

---

## What makes Auralis distinctive

### 1. Adaptive mastering, not fixed presets

Instead of a static EQ, Auralis analyzes each track into a **25-dimensional fingerprint**
(spectral, dynamic, temporal, harmonic, stereo) and derives mastering parameters from it. The
default engine maps that fingerprint into a continuous processing space rather than snapping to
a preset. See [subsystems/dsp-engine.md](../subsystems/dsp-engine.md) and
[subsystems/fingerprinting.md](../subsystems/fingerprinting.md).

### 2. Real-time streaming with gapless chunks

Enhanced audio is processed in **15-second chunks at 10-second intervals with 5-second
overlap**, crossfaded with equal-power curves so there are no audible seams. Chunk geometry has
a **single source of truth** ([`chunk_boundaries.py`](../../auralis-web/backend/core/chunk_boundaries.py))
— never hand-roll chunk counting.

### 3. Rust for the hot path

The heavy analysis DSP (harmonic/percussive separation, pitch detection, chromagram, and the
full native fingerprint) runs in Rust via PyO3, with a standalone gRPC fingerprint server as
the primary extraction path. **There is no Python fallback** — the Rust module must be built
(`maturin develop`) before first run.

---

## Critical invariants (project-wide)

These hold across the audio pipeline and are asserted, not assumed:

```python
assert len(output) == len(input)               # never change sample count (gapless!)
assert isinstance(output, np.ndarray)          # always NumPy, never lists
assert output.dtype in (np.float32, np.float64)
output = audio.copy()                          # never modify in place
```

Plus:

- **No NaN/Inf** escapes the pipeline (`validate_audio_finite` / `sanitize_audio`).
- **All DB access goes through repositories** ([`auralis/library/repositories/`](../../auralis/library/repositories/)) — never raw SQL.
- **Shared backend state is lock-guarded** — `asyncio.Lock` for event-loop state,
  `threading.RLock` for CPU/thread-pool state, `contextvars` for per-stream isolation.

The `verify-dsp` skill checks the six audio invariants across the pipeline.

---

## Source-of-truth registry

When docs and code disagree, these win:

| Fact | Source of truth |
|------|-----------------|
| Product version | [`auralis/version.py`](../../auralis/version.py) (not `pyproject.toml`, not the frontend constant, not `create_app`'s "1.0.0") |
| Fingerprint dimension semantics/units | [`analysis/fingerprint/schema.py`](../../auralis/analysis/fingerprint/schema.py) |
| Chunk geometry | [`backend/core/chunk_boundaries.py`](../../auralis-web/backend/core/chunk_boundaries.py) |
| DB schema version | [`auralis/library/migration_manager.py`](../../auralis/library/migration_manager.py) (v16) |
| Fingerprint algorithm version | [`auralis/__version__.py`](../../auralis/__version__.py) (`FINGERPRINT_ALGORITHM_VERSION`) |

---

## Where to go next

- **See it work end to end** → [data-flow.md](data-flow.md)
- **Find your way around the files** → [module-map.md](module-map.md)
- **Set up and contribute** → [../CONTRIBUTING.md](../CONTRIBUTING.md)
- **Deep dives** → [DSP engine](../subsystems/dsp-engine.md) ·
  [Fingerprinting](../subsystems/fingerprinting.md) ·
  [Backend API](../subsystems/backend-api.md) · [Frontend](../subsystems/frontend.md)
