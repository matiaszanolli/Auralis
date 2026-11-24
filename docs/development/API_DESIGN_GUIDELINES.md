# API Design Guidelines

The REST conventions the backend routers follow. They describe what
[`auralis-web/backend/routers/`](../../auralis-web/backend/routers/) does today; a new route
matches its neighbours. The route catalog is in [backend-api.md](../subsystems/backend-api.md), the
WebSocket protocol in [WEBSOCKET_API.md](../../auralis-web/backend/WEBSOCKET_API.md), database
access in [REPOSITORY_PATTERN.md](REPOSITORY_PATTERN.md).

## Router structure

- One `create_<domain>_router(...)` factory per router, returning a fresh `APIRouter`
  (`tags=[...]`), called from `config/routes.py::setup_routers`. Handlers are plain module-level
  `async def` functions registered with `router.add_api_route(path, handler, methods=[...],
  response_model=...)`, not decorated on a module-level router. The example is
  `routers/tracks.py::create_tracks_router`.
- Collaborators come from the factory's getters, never imported singletons. The factory stores
  them in a per-router `RouterDeps` holder (`routers/dependencies.py`) bound with a router-level
  dependency; handlers read them through `Depends(...)` providers
  (`routers/repo_deps.py::RepositoryFactoryDeps` for the repository factory). A missing component
  is a 503 through `require_service` / `require_repository_factory`.
- A router that outgrows 300 lines splits into siblings (`*_models.py`, `*_deps.py`, topic
  modules) that its factory imports; siblings are not registered on their own.
- Every handler is `async def`. Blocking work (repository calls, file I/O, DSP, image work) goes
  through `asyncio.to_thread` or a `run_in_*_executor` wrapper; never run it on the event loop.

## Paths, naming and verbs

- Resources are plural nouns under `/api/`: `/api/albums`, `/api/playlists/{playlist_id}`,
  `/api/library/tracks/{track_id}`. Path parameters are snake_case and typed
  `Annotated[int, Path(ge=1)]`.
- Reads are `GET`, creation is `POST` on the collection, partial update `PUT`, removal `DELETE`.
  Actions that are not CRUD are `POST` on a verb sub-path in kebab-case:
  `/api/player/queue/add-track`, `/api/processing/upload-and-process`,
  `/api/player/enhancement/toggle`. The exception is
  `POST /api/settings/scan-folders/delete`, which takes a body.
- JSON field names are snake_case (`track_id`, `has_more`, `retry_after_seconds`). Python
  identifiers follow PEP 8; handler names are verbs (`get_tracks`, `set_track_favorite`).
- Success is HTTP 200 with a body; routes do not use 201 or 204.

## Request and response models

- Every route declares `response_model=`. The only exceptions are the two file responses
  (`GET /api/albums/{album_id}/artwork`, `GET /api/processing/job/{job_id}/download`), which
  return `FileResponse`.
- Models are Pydantic v2 `BaseModel`s in the router's `*_models.py` (or `schemas/` when shared),
  with `Field(description=...)` on non-obvious fields.
- Request bodies are bounded: ids use `schemas/request_bounds.py` (`TrackId`, `QueueIndex`,
  `TrackIdList` with `MAX_TRACK_ID_LIST`), enumerations are `Literal`s (an unknown value is a 422,
  not a silent default), numeric ranges use `Field(ge=, le=)`, and partial-update models set
  `ConfigDict(extra="forbid")` (`routers/settings_models.py`).
- Mutations answer `{"message": str, ...identifying fields}`, for example
  `TrackFavoriteResponse` and `routers/player_models.py::SeekResponse`. Lists are keyed by the
  domain name, not `items`.
- Handlers never return ORM objects or raw rows; they go through `routers/serializers.py` or build
  the response model. Server filesystem paths are never part of a response.

## Pagination

Paginated list routes take `limit` and `offset` and return one envelope:

```python
async def get_tracks(
    limit: int = limit_query(),      # 1-200, default 50
    offset: int = offset_query(),    # 0 up to the SQLite integer maximum
    search: str | None = None,
    order_by: Literal['title', 'created_at', ...] = 'created_at',
    order: SortOrder = None,         # 'asc' | 'desc'
    repos: Any = Depends(_repo_deps.get_repos),
) -> dict[str, Any]:
    tracks, total = await asyncio.to_thread(repos.tracks.get_all, ...)
    return paginated("tracks", serialize_tracks(tracks), total, offset, limit)
```

`routers/pagination.py::paginated` builds `{<key>: [...], total, offset, limit, has_more}`;
`has_more` is computed from the actual page length by `compute_has_more`. Repositories return
`tuple[list[T], int]` for paged queries, `T | None` for single lookups and `bool` for
set/delete operations that can miss; see REPOSITORY_PATTERN.md.

## Errors

- Handlers raise `HTTPException`, normally the subclasses in `routers/errors.py`, never bare exceptions:
  `NotFoundError("Track", track_id)` (404, "Track 5 not found"), `BadRequestError(detail)` (400),
  `ServiceUnavailableError` (503), `UnprocessableAudioFileError` (422), `InternalServerError`
  (500). Validation failures from Pydantic are handled globally and answer 422 with
  `{"detail": "Validation error", "errors": [{"field", "message"}]}`.
- The body shape is `{"detail": "<message>"}`. A rate-limit 429 adds `rule` and
  `retry_after_seconds`.
- Wrap handlers that touch the database in `@with_error_handling("get tracks")`
  (`routers/dependencies.py`): `HTTPException` passes through; other exceptions map by type in
  `errors.py::handle_query_error` (transient SQLite error 503, vanished file 404, permission 403,
  anything else a generic 500).
- Service-layer failures (`services/errors.py`) map to HTTP by type through
  `errors.py::raise_for_service_error`, never by matching message text.
- Messages are fixed or user-safe. Never put exception text, server paths or client-controlled
  strings in a response; log the detail server-side (`sanitize_log_value` for untrusted values).
  Component outages (`None` after startup rollback or worker death) are 503, not 500.

## Streaming and real-time

Audio is delivered over the WebSocket only; there are no REST chunk or MSE routes. REST mutations
that change shared state broadcast the change with `websocket/outbound_messages.py::broadcast_typed`
(each message type has a `TypedDict` payload) and are documented in WEBSOCKET_API.md.

## Checklist for a new route

1. Handler is `async def`, blocking work off the loop.
2. `response_model=` set; request model bounded.
3. Path ids `Path(ge=1)`; list routes use `limit_query`, `offset_query` and `paginated`.
4. Errors via `routers/errors.py`; DB handlers wrapped in `with_error_handling`.
5. Registered in the router's factory, with an entry in the rate-limit table
   (`config/middleware/rate_limit.py`) if it is expensive.
6. If it mutates shared state, it broadcasts a typed WebSocket message and the frontend registry
   (`auralis-web/frontend/src/types/ws/registry.ts`) and WEBSOCKET_API.md are updated.
