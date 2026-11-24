# Repository Pattern in Auralis

All database access goes through classes in
[`auralis/library/repositories/`](../../auralis/library/repositories/). Routers, services, the
player and the scanner never open a session, write SQL or call `session.commit()`; they call a
repository method and get back **detached** ORM objects, plain values or `(rows, total)`.

This page is the how-to for *writing* a repository method. The architecture around it (engine,
pragmas, migrations, the scanner, the full eager-loading rationale) is in
[../subsystems/library.md](../subsystems/library.md); read §4 there first.

## The rules

1. Extend `BaseRepository` ([`base.py`](../../auralis/library/repositories/base.py)); it stores
   `session_factory` and provides the session helpers below. Add an `__init__` only to store extra
   collaborators, and call `super().__init__(session_factory)` first.
2. One session per method call, opened with a helper, never held across calls, `await`s or
   engine locks.
3. Use SQLAlchemy 2.0 `select()` with `session.execute(...)`. Not `session.query(...)`.
4. Return detached objects, and make sure every relationship the caller (or `to_dict()`) will
   read is eager-loaded before they detach.
5. Writes commit inside the repository. A failed write rolls back; callers never roll back.
6. Register new repositories in `repositories/__init__.py` and as a lazy property on
   `RepositoryFactory` ([`factory.py`](../../auralis/library/repositories/factory.py)). The
   factory is the only constructor callers use.

## Session helpers

| Helper | Use for | Behaviour |
|--------|---------|-----------|
| `_session_scope()` | reads, and writes that report failure by raising | yields a session, rolls back if an exception escapes, always closes |
| `_write_session_scope()` | **read-then-write** methods | the same, after `BEGIN IMMEDIATE`, so concurrent writers queue and each reads the previous one's committed rows |
| `_guarded("Failed to X", write=False)` | writes that report failure through a return value | like the scopes, but an escaping `Exception` is logged at ERROR and swallowed; the line after the `with` returns the failure default |
| `_first_detached(session, stmt)` | get-one | first row or `None`, then `session.expunge_all()` |
| `_all_detached(session, stmt)` | get-many | list of rows, then `session.expunge_all()` |

`expunge_all()` (rather than `expunge(obj)`) matters: a per-object expunge does not cascade, so
the eager-loaded relatives stay attached and misbehave later.

`_guarded` makes failure and "not found" look the same to the caller (`None` / `False` / `0`).
That is the existing contract; do not rely on telling them apart.

## Reads

### Get one

```python
def get_by_id(self, track_id: int) -> Track | None:
    with self._session_scope() as session:
        return self._first_detached(
            session,
            select(Track).options(*_track_eager_options()).where(Track.id == track_id),
        )
```

(from `TrackRepositoryLookupMixin`). `_first_detached` applies `.unique()`, which joined
collection loads require.

### Paginated list: `(rows, total)`

```python
def get_all(self, limit: int = 50, offset: int = 0, order_by: str = 'title',
            order: str | None = None) -> tuple[list[Album], int]:
    with self._session_scope() as session:
        total = session.execute(select(func.count()).select_from(Album)).scalar_one()
        albums = self._all_detached(
            session,
            select(Album)
            .options(*_ALBUM_LIST_OPTIONS)
            .order_by(*_album_order_by(order_by, order))
            .limit(limit).offset(offset),
        )
        return albums, total
```

- Pagination always returns `(rows, total)` so the UI can show "N of M".
- **Whitelist `order_by`** against a fixed set of columns; never `getattr(Model, user_input)`.
- Order with `sort_terms(column, Model.id, descending=...)`: text sorts `COLLATE NOCASE`, NULLs
  sort last, and the primary key is the tie-breaker so `LIMIT`/`OFFSET` pages neither overlap nor
  skip rows.
- For counts or sums per row (track count per album), use `with_expression` with
  `correlated_count` / `correlated_sum` from `base.py` instead of loading children.

### Search

Use `contains_text(column, query)` from
[`text_search.py`](../../auralis/library/repositories/text_search.py): it case-folds in every
script and treats `%`, `_` and `\` literally. Do not hand-roll `ilike(f"%{q}%")`: that folds ASCII
only and treats `%` as a wildcard.

### Batched lookups

`WHERE id IN (...)` over a caller-sized list must be batched below SQLite's variable limit:

```python
for batch in _iter_in_batches(unique_ids):          # track_repository.py
    rows = session.execute(
        select(Track).options(*_track_eager_options()).where(Track.id.in_(batch))
    ).scalars().unique().all()
    for row in rows:
        session.expunge(row)
```

## Eager loading

- **Many-to-many collections: `selectinload`, never `joinedload`.** (`Track.artists`,
  `Track.genres`, `Artist.tracks`, `Genre.tracks`, `Playlist.tracks`.) Joined, SQLite scans the
  whole association table and one `get_by_id` costs time proportional to the library.
- Many-to-one (`Track.album`, `Album.artist`) may be joined; use `selectinload` when the query is
  paginated or `DISTINCT` so a join cannot multiply rows.
- **Define the option tuple once at module scope** and reuse it on every read path of that
  entity:

  ```python
  _GENRE_LOAD_OPTIONS = (selectinload(Genre.tracks),)
  ...
  select(Genre).where(Genre.id == genre_id).options(*_GENRE_LOAD_OPTIONS)
  ```

  Existing tuples: `_ALBUM_DETAIL_OPTIONS`, `_ALBUM_LIST_OPTIONS`, `_ARTIST_DETAIL_OPTIONS`,
  `_ARTIST_LIST_OPTIONS`, `_GENRE_LOAD_OPTIONS`, `_PLAYLIST_DETAIL_OPTIONS`, and the function
  `_track_eager_options()`. A parent that hands tracks to `Track.to_dict()` composes
  `nested_track_options(Parent.tracks)`. Inline option lists are how a sibling method ends up
  missing a relationship.
- `to_dict()` reads relationships through `_safe_collection` / `_safe_scalar`
  ([`models/_helpers.py`](../../auralis/library/models/_helpers.py)); a WARNING from them names a
  missing `selectinload`. Fix the repository, not the log level.

### After a commit

`commit()` expires the instance. `session.refresh(obj)` reloads columns but **does not re-apply
loader options**, so relationships are unloaded and raise `DetachedInstanceError` once the object
is expunged. Either:

```python
session.commit()
session.refresh(genre)
_ = genre.tracks            # touch it while still attached (GenreRepository.create)
session.expunge(genre)
```

or, preferred when several relationships matter, re-query with the options and detach the result
(`_reload_detached(session, Track.id == track.id)` in
[`track_repository_mutation.py`](../../auralis/library/repositories/track_repository_mutation.py),
which `TrackRepository.add` also does inline).

## Writes

### Failure reported by return value

```python
def update_by_filepath(self, filepath, track_info, *, replace_tags=False) -> Track | None:
    with self._guarded("Failed to update track", write=True) as session:
        track = session.execute(
            select(Track).where(Track.filepath_key == make_filepath_key(filepath))
        ).scalars().first()
        if not track:
            return None
        ...                                   # mutate
        session.commit()
        return _reload_detached(session, Track.filepath_key == make_filepath_key(filepath))
    return None
```

`write=True` is right whenever the method reads rows or resolves get-or-create entities and then
writes: it takes SQLite's write lock before the first read. Return a detached object from inside
the `with`; the trailing `return None` is the failure default.

### Failure reported by raising

```python
def create(self, name: str, **kwargs) -> Genre:
    with self._session_scope() as session:
        try:
            genre = Genre(name=name)
            session.add(genre)
            session.commit()
            session.refresh(genre)
            _ = genre.tracks
            session.expunge(genre)
            return genre
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create genre: {e}")
            raise
```

`_session_scope` already rolls back an escaping exception, so the explicit `rollback()` is
redundant and only needed if the method logs between the failure and the re-raise. Do not
swallow the exception unless the method's contract is a failure default (then use `_guarded`).

### Conventions that bite

- **Identity is `filepath_key`**, from `make_filepath_key()`; compare it, never `filepath`, and
  set it on every insert.
- **Get-or-create** is `INSERT ... ON CONFLICT DO NOTHING` then re-select (`_get_or_create` in
  `track_repository_lifecycle.py`), not a SAVEPOINT or a try/except around `add`.
- **Allow-list writable columns** for any path fed by a request body
  (`_METADATA_WRITABLE_COLUMNS`); never `setattr` from raw dict keys.
- **Deleting tracks** goes through `delete_tracks_by_ids(session, ids)` in the caller's
  transaction; it clears association rows, compacts playlist positions and prunes orphaned
  albums, artists and genres.
- **Bulk deletes** use `delete(Model).where(...)`; pass
  `execution_options(synchronize_session=False)` when nothing in the session needs syncing.

## Adding a repository

1. Create `repositories/<entity>_repository.py` with `class XRepository(BaseRepository)`. If it
   grows past about 300 lines, split by concern into mixins that each extend `BaseRepository`
   (see `TrackRepository`, `PlaylistRepository`), keeping one facade class.
2. Define the module-scope eager-load tuple(s) for the entity.
3. Export it from `repositories/__init__.py`; add a property to `RepositoryFactory` using
   `self._cached("_x_repo", lambda: XRepository(self.session_factory))` and a matching
   `_x_repo: ... | None = None` in `__init__`.
4. If other code reads it off the database object, add a forwarding property to
   `RepositoryAccessorsMixin` ([`database_accessors.py`](../../auralis/library/database_accessors.py)).
5. If it adds a table or column, add the model change **and** the next migration (see
   [library.md §6](../subsystems/library.md#6-migrations)).

Checklist for review: extends `BaseRepository`; every method uses a session helper; every read
path has the entity's option tuple; no `session.query`; `order_by` whitelisted; list methods
return `(rows, total)`; post-commit objects reloaded or touched before expunge; type hints and a
docstring on public methods; no raw SQL outside a migration.

## Anti-patterns

| Do not | Do instead |
|--------|------------|
| open `session_factory()` in a router, service or the player | add a repository method; call it through `asyncio.to_thread` from async code |
| `session.commit()` or `object_session(obj)` on a returned object | return a value from a repository method that commits |
| return an attached object, or `expunge(obj)` one by one | `_first_detached` / `_all_detached` |
| `joinedload` a many-to-many | `selectinload` in the entity's option tuple |
| inline `.options(...)` lists that differ per method | one module-scope tuple per entity and read shape |
| `refresh()` then expunge | touch the relationship first, or `_reload_detached` |
| `ilike(f"%{q}%")` | `contains_text(column, q)` |
| order by a client-supplied column name | whitelist, then `sort_terms` |
| compare `Track.filepath == path` | `Track.filepath_key == make_filepath_key(path)` |

## Testing

Repositories are instances built from a session factory; they are never called as class methods.

```python
def test_add_and_retrieve(library_database):            # tests/conftest.py fixture
    repo = library_database.tracks                       # a TrackRepository
    track = repo.add({"title": "Test Track", "filepath": "/tmp/test.wav"})
    assert track is not None and track.id is not None
    assert repo.get_by_id(track.id).title == "Test Track"
    assert repo.delete(track.id)
```

- The `library_database` fixture opens a real `LibraryDatabase` on a temp file (migrated,
  foreign keys on). `LibraryDatabase(':memory:')` does not work.
- The `session_factory` fixture builds a bare engine **without** the foreign-key pragma; use it
  only for tests that do not depend on FK behaviour or cascades.
- Seed `Artist` rows with `normalized_name`; without it `TrackRepository.add()` for that artist
  rolls back and returns `None`, so datasets come out silently empty.
- Test the eager-load contract directly: fetch through the repository, then read each relationship
  that `to_dict()` uses on the detached object and assert no warning was logged.
- Do not run backend tests that boot the app against your real `~/.auralis`; set `HOME` to a
  scratch directory.

## Troubleshooting

| Symptom | Cause and fix |
|---------|---------------|
| `DetachedInstanceError`, or an empty `artists` / `genres` in a payload plus a `_safe_collection` WARNING | a read path or post-commit path is missing its eager-load; add the option tuple or reload |
| "database is locked" | a transaction held too long or a read-then-write method without `_write_session_scope`; keep sessions short |
| method returns `None` and the log says "Failed to ..." | a `_guarded` method swallowed an exception; read the ERROR line |
| duplicate rows on a case-insensitive filesystem | lookup compared `filepath` instead of `filepath_key` |
| "no such table" / missing column | the model changed without a migration; see [library.md §6](../subsystems/library.md#6-migrations) |

## Related

[../subsystems/library.md](../subsystems/library.md) ·
[TESTING_GUIDELINES.md](TESTING_GUIDELINES.md) ·
[SQLAlchemy 2.0 session docs](https://docs.sqlalchemy.org/en/20/orm/session.html)
