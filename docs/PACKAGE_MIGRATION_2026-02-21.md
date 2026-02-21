# Backend Package Migration — 2026-02-21

Reorganised 19 loose modules from the `auralis-web/backend/` root into the
existing and four new sub-packages.

## New package structure

```
auralis-web/backend/
├── core/                   ← audio pipeline (existed, 6 new modules added)
│   ├── audio_stream_controller.py  ← was: backend root
│   ├── chunked_processor.py        ← was: backend root
│   ├── processing_engine.py        ← was: backend root
│   ├── proactive_buffer.py         ← was: backend root
│   ├── state_manager.py            ← was: backend root
│   └── streamlined_worker.py       ← was: backend root
├── analysis/               ← NEW — fingerprinting & track analysis
│   ├── __init__.py
│   ├── fingerprint_generator.py    ← was: backend root
│   ├── fingerprint_queue.py        ← was: backend root
│   ├── analysis_extractor.py       ← was: backend root
│   └── track_analysis_cache.py     ← was: backend root
├── services/               ← adaptive learning (existed, 3 new modules added)
│   ├── learning_system.py          ← was: backend root
│   ├── self_tuner.py               ← was: backend root
│   └── audio_content_predictor.py  ← was: backend root
├── monitoring/             ← NEW — system observability
│   ├── __init__.py
│   ├── metrics_collector.py        ← was: backend root
│   └── memory_monitor.py           ← was: backend root
├── websocket/              ← NEW — WS protocol & security
│   ├── __init__.py
│   ├── websocket_protocol.py       ← was: backend root
│   └── websocket_security.py       ← was: backend root
├── security/               ← NEW — path validation
│   ├── __init__.py
│   └── path_security.py            ← was: backend root
└── routers/                ← REST handlers (existed, 1 new module added)
    └── processing_api.py           ← was: backend root
```

## Import translation table

| Old (flat) import | New import |
|---|---|
| `from chunked_processor import X` | `from core.chunked_processor import X` |
| `from audio_stream_controller import X` | `from core.audio_stream_controller import X` |
| `from processing_engine import X` | `from core.processing_engine import X` |
| `from proactive_buffer import X` | `from core.proactive_buffer import X` |
| `from state_manager import X` | `from core.state_manager import X` |
| `from streamlined_worker import X` | `from core.streamlined_worker import X` |
| `from fingerprint_generator import X` | `from analysis.fingerprint_generator import X` |
| `from fingerprint_queue import X` | `from analysis.fingerprint_queue import X` |
| `from analysis_extractor import X` | `from analysis.analysis_extractor import X` |
| `from track_analysis_cache import X` | `from analysis.track_analysis_cache import X` |
| `from learning_system import X` | `from services.learning_system import X` |
| `from self_tuner import X` | `from services.self_tuner import X` |
| `from audio_content_predictor import X` | `from services.audio_content_predictor import X` |
| `from metrics_collector import X` | `from monitoring.metrics_collector import X` |
| `from memory_monitor import X` | `from monitoring.memory_monitor import X` |
| `from websocket_protocol import X` | `from websocket.websocket_protocol import X` |
| `from websocket_security import X` | `from websocket.websocket_security import X` |
| `from path_security import X` | `from security.path_security import X` |
| `from processing_api import X` | `from routers.processing_api import X` |

## Files touched (import updates)

### Backend — moved files with internal cross-references updated
- `core/audio_stream_controller.py` — imports chunked_processor, fingerprint_generator, fingerprint_queue
- `core/chunked_processor.py` — sys.path arithmetic updated (parent.parent instead of parent)
- `core/proactive_buffer.py` — lazy import of chunked_processor
- `core/streamlined_worker.py` — lazy import of chunked_processor
- `services/self_tuner.py` — imports learning_system, memory_monitor, audio_content_predictor
- `services/learning_system.py` — lazy import of audio_content_predictor
- `routers/processing_api.py` — imports processing_engine

### Backend — non-moved files updated
- `main.py` — proactive_buffer, chunked_processor
- `config/startup.py` — state_manager, fingerprint_generator, fingerprint_queue, processing_api, processing_engine, streamlined_worker
- `config/routes.py` — processing_api
- `routers/system.py` — audio_stream_controller, websocket_security, chunked_processor (×2)
- `routers/library.py` — fingerprint_queue (×2)
- `routers/similarity.py` — fingerprint_queue (×4)
- `routers/enhancement.py` — path_security, chunked_processor (×2), get_last_content_profile
- `schemas.py` — path_security
- `services/navigation_service.py` — state_manager
- `services/recommendation_service.py` — chunked_processor (×2)

### Tests — 24 files updated
`tests/boundaries/`, `tests/security/`, `tests/integration/`, `tests/backend/`

## Modules that stayed at the backend root

| File | Reason |
|---|---|
| `main.py` | App entry point |
| `schemas.py` | API contract, imported everywhere |
| `helpers.py` | Shared pagination/response utilities |
| `middleware.py` | App-level HTTP middleware |
| `player_state.py` | Shared Pydantic model (state + TrackInfo) |
| `version.py` | Version constant |

## Notes

- All moves done with `git mv` to preserve file history.
- `chunked_processor.py` had a hard-coded `sys.path` block to locate the
  backend root; updated from `Path(__file__).parent` to
  `Path(__file__).parent.parent` now that the file lives in `core/`.
- `analysis_extractor.py` already used a relative import
  (`from .track_analysis_cache import …`); this now works correctly
  inside the `analysis/` package.
- `pytest.ini` `pythonpath = auralis-web/backend` unchanged — tests still
  resolve all packages correctly via the backend root.
