# Subsystem: Library (SQLite, Repositories, Migrations, Scanner)

[`auralis/library/`](../../auralis/library/) is the persistence layer: one SQLite file
(`~/.auralis/library.db` by default) holding tracks, albums, artists, genres, playlists, 25D
fingerprints, the similarity graph, user settings and processing jobs, plus the code that opens
it, migrates it, fills it from disk and hands out data to the rest of the app.

> **Scope.** The database object, models, repositories, migrations and the folder scanner. How
> to *write* a repository method is in
> [../development/REPOSITORY_PATTERN.md](../development/REPOSITORY_PATTERN.md). How fingerprints are
> computed and scheduled is in [fingerprinting.md](fingerprinting.md); the HTTP surface over the
> library is in [backend-api.md](backend-api.md).

---

## 1. Layout

| Piece | Where | Role |
|-------|-------|------|
| `LibraryDatabase` | [`database.py`](../../auralis/library/database.py) (+ [`database_engine.py`](../../auralis/library/database_engine.py), [`database_accessors.py`](../../auralis/library/database_accessors.py), [`scan_coordinator.py`](../../auralis/library/scan_coordinator.py)) | composition root: migrate, engine, sessions, repositories, scan slots, shutdown |
| Models | [`models/`](../../auralis/library/models/) | SQLAlchemy 2.0 declarative classes, association tables, `_helpers.py` |
| Repositories | [`repositories/`](../../auralis/library/repositories/) | all data access; `RepositoryFactory` hands out 12 of them |
| Migrations | [`migration_manager.py`](../../auralis/library/migration_manager.py) and siblings, SQL in [`migrations/`](../../auralis/library/migrations/) | versioned, atomic, backed-up schema upgrades |
| Scanner | [`scanner/`](../../auralis/library/scanner/) (+ [`scan_models.py`](../../auralis/library/scan_models.py), [`scan_paths.py`](../../auralis/library/scan_paths.py)) | folder walk, tag extraction, add/update/skip |
| On-disk helpers | [`data_dir.py`](../../auralis/library/data_dir.py), [`artwork.py`](../../auralis/library/artwork.py), [`sidecar_manager.py`](../../auralis/library/sidecar_manager.py), [`path_key.py`](../../auralis/library/path_key.py) | cache locations, album art extraction, `.25d` sidecars, path identity |
| Tag editing | [`metadata_editor/`](../../auralis/library/metadata_editor/) | read/write tags with backup and rollback (separate from the DB) |

Everything outside this package reaches the database through
`LibraryDatabase.repositories` (a `RepositoryFactory`) or the forwarding accessors
(`db.tracks`, `db.albums`, ...). No router, service or player code builds a session.

---

## 2. `LibraryDatabase`

`LibraryDatabase(database_path=None)` ([`database.py`](../../auralis/library/database.py)) is the only
thing that opens the file. Construction order:

1. `resolve_database_path`: default `DEFAULT_DB_PATH`; hardens `~/.auralis` to `0700` when the
   database lives there.
2. `register_database_location`: artwork, the `.25d` cache and thumbnails follow the open
   database (`data_dir.py`; `AURALIS_DATA_DIR` overrides the default root).
3. `check_and_migrate_database(path, auto_backup=True)`. A failure raises `MigrationError`; the
   caller must not proceed against a half-migrated file (§6).
4. `create_library_engine`, `sessionmaker`, `create_schema` (`create_all` plus
   `create_missing_declared_indexes`), owner-only permissions on the file and its `-wal` / `-shm`.
5. `RepositoryFactory(SessionLocal)`; then `tracks.backfill_filepath_keys()` (idempotent,
   failure only warns).
6. `ScanCoordinator`, and `atexit.register(self.shutdown)`.

### Engine configuration

Defined in `create_library_engine`; the numeric constants live in
[`constants.py`](../../auralis/library/constants.py) and are shared by every engine that opens the
file (the library engine, the migration engine and `FingerprintService`'s own engine), because
the engine with the shortest wait is the one that raises "database is locked".

| Setting | Value |
|---------|-------|
| Pool | `pool_size=5`, `max_overflow=5`, `pool_pre_ping=True` |
| Journal | `PRAGMA journal_mode=WAL`, set through `enable_wal` (retried on lock contention) |
| Durability | `synchronous=NORMAL` |
| Waits | `connect_args["timeout"]=SQLITE_CONNECT_TIMEOUT_S` (15 s); `PRAGMA busy_timeout=SQLITE_BUSY_TIMEOUT_MS` (60 000 ms) |
| Memory | `cache_size=-8192` (8 MB **per connection**), `temp_store=MEMORY` |
| Integrity | `PRAGMA foreign_keys=ON` |
| Log hygiene | `hide_parameters=True`: a DB error never prints bound paths or tags |

`check_same_thread=False`: connections cross threads (to_thread, scanner, workers). Sessions are
short-lived and per call, so the pool stays small; SQLite allows one writer, WAL lets readers
continue.

`LibraryDatabase(':memory:')` does not work (the pool settings are rejected); use a temp file.
A case-folding SQL function `casefold()` is registered on every `Engine` connect
([`repositories/text_search.py`](../../auralis/library/repositories/text_search.py)) because SQLite's
`lower()` and `LIKE` fold ASCII only.

### Scan slots

`ScanCoordinator` hangs off the database object, not the scanner, because every caller creates a
fresh `LibraryScanner` per scan. It owns three pieces of state:

- **slots:** `try_acquire_scan_slot()` reads `max_concurrent_scans` from settings on every call;
- **paths:** `try_reserve_scan_paths()` reserves symlink-resolved directories and rejects any that
  equal, contain or lie inside an active scan's directory (`scan_paths.paths_overlap`);
- **exclusive access:** `try_begin_exclusive_access()` is granted only when no scan holds a slot
  and then refuses every new scan; the library reset route holds it so a scan cannot re-insert
  rows the reset is deleting.

Slot count and the exclusive flag share one lock, so "is a scan running" and "may one start"
cannot disagree. `is_scanning()` is a live read of that counter.

### Shutdown

`shutdown()` (atexit, `__del__`, and the backend's ordered shutdown, which calls it last):
`PRAGMA wal_checkpoint(TRUNCATE)`, `PRAGMA optimize`, `engine.dispose()`, then `engine = None` in
a `finally` so `__del__` does not retry. Idempotent. `cleanup_incomplete_fingerprints()` releases
**every** fingerprint claim in the table and is called only by the long-lived backend at startup,
never from `__init__` (a second process on the same library would wipe live claims).

---

## 3. Models

All models extend `Base`; most add `TimestampMixin` (`created_at`, `updated_at`, UTC, with a
`server_default` so raw SQL gets timestamps too). Exported from
[`models/__init__.py`](../../auralis/library/models/__init__.py).

| Model | Table | Notes |
|-------|-------|-------|
| `Track` | `tracks` | `filepath` (as discovered, unique) and `filepath_key` (the value lookups compare, unique); `file_mtime` is the scanner's change watermark; `lyrics` / `comments` are large Text columns |
| `Album` | `albums` | owned by an artist (`artist_id`, nullable); unique per title and owner via partial indexes |
| `Artist` | `artists` | `normalized_name` is the identity used for get-or-create |
| `Genre` | `genres` | |
| `Playlist` | `playlists` | `is_smart` / `smart_criteria` are stored but nothing evaluates them |
| `TrackFingerprint` | `track_fingerprints` | one row per track (`track_id` unique, `ondelete=CASCADE`); the 25 dimensions plus status and claim columns |
| `SimilarityGraph` | `similarity_graph` | KNN edges `(track_id, similar_track_id, rank, distance)`; unique edge index |
| `UserSettings` | `user_settings` | the single app-settings row (`SettingsRepository`) |
| `ProcessingJobRecord` | `processing_jobs` | persisted REST processing jobs |
| `SchemaVersion` | `schema_version` | one row per applied migration |

Association tables in [`models/base.py`](../../auralis/library/models/base.py): `track_artist`
(with `position`, the artist's index in the tag, so `Track.artists[0]` is the primary artist),
`track_genre`, and `track_playlist` (composite primary key plus `position`). Each side of each
association table carries its own index, because SQLite indexes only the parent key of a foreign
key.

`Track.fingerprint` and `Track.similar_tracks` use `passive_deletes=True`: the database's
`ON DELETE CASCADE` removes the children, since both declare `track_id` non-null.

### Detached instances and `models/_helpers.py`

Repositories `expunge()` everything they return, so any relationship a query did not eager-load
raises `DetachedInstanceError` when `to_dict()` touches it. Two rules, both required:

1. Every repository read path carries the right `selectinload(...)` options (§4).
2. `to_dict()` reads relationships through `_safe_collection(instance, attr)` /
   `_safe_scalar(instance, attr)` in
   [`models/_helpers.py`](../../auralis/library/models/_helpers.py). They degrade to `[]` / `None` and
   log a WARNING naming the missing eager-load, turning a missed option into a diagnosable
   degraded field rather than a 500 far from the cause. A WARNING from them is a bug in a
   repository, not noise.

---

## 4. Repositories

[`repositories/__init__.py`](../../auralis/library/repositories/__init__.py) exports `BaseRepository`,
`RepositoryFactory` and the twelve repositories. `RepositoryFactory`
([`factory.py`](../../auralis/library/repositories/factory.py)) builds each lazily behind a
double-checked lock (`_cached`), so every thread gets the same instance. Lazy matters:
`FingerprintSchedulerRepository` keeps per-process claim cursors, and `AlbumRepository` creates
the artwork directory on construction.

| Accessor | Class | Concern |
|----------|-------|---------|
| `tracks` | `TrackRepository` | lifecycle, lookup, search, mutation, relocation, maintenance (six mixins) |
| `albums` | `AlbumRepository` | albums, artwork (`AlbumArtworkMixin`) |
| `artists` | `ArtistRepository` | artists, artist pages |
| `genres` | `GenreRepository` | genres |
| `playlists` | `PlaylistRepository` | CRUD, query, membership, ordering (four mixins) |
| `stats` | `StatsRepository` | library counts and aggregates |
| `settings` | `SettingsRepository` | the `user_settings` row |
| `fingerprints` | `FingerprintRepository` | fingerprint CRUD, upsert, query, similarity lookups |
| `fingerprint_scheduler` | `FingerprintSchedulerRepository` | atomic claim of the next track to fingerprint |
| `fingerprint_stats` | `FingerprintStatsRepository` | coverage and status aggregates; stale-claim cleanup |
| `similarity_graph` | `SimilarityGraphRepository` | KNN edge persistence and neighbour reads |
| `processing_jobs` | `ProcessingJobRepository` | processing job rows |

`RepositoryFactory.reset_library()` deletes every content row in one transaction, children before
parents; callers pause background workers and take exclusive access first.

### `BaseRepository` semantics

[`repositories/base.py`](../../auralis/library/repositories/base.py) holds the session lifecycle:

- `get_session()` opens a session from the factory.
- `_session_scope()`: yields a session, **closes it**, and **rolls back if an exception
  escapes** (rollback failure never masks the original error). The caller still commits.
  A method that catches its own failure and returns keeps the objects it has not yet returned
  attached; only escaping exceptions trigger the rollback.
- `_write_session_scope()`: `_session_scope()` plus `BEGIN IMMEDIATE`, for read-then-write
  methods. pysqlite begins a transaction at the first write, so without it two concurrent
  removals or reorders compute from the same snapshot. It serialises against every writer.
- `_guarded(message, write=False)`: `_session_scope()` that logs an escaping `Exception` at
  ERROR as `"<message>: <error>"` and swallows it, so the line after the `with` returns the
  method's failure default (`None` / `False` / `0`). Failure is therefore indistinguishable from
  "not found" to the caller.
- `_first_detached` / `_all_detached`: run a `select`, then `expunge_all()` so eager-loaded
  relatives detach with their parents.

Module-level helpers: `escape_like`, `sort_terms` (NOCASE text, NULLs last, primary-key
tie-breaker so LIMIT/OFFSET pages are stable), `correlated_count`, `correlated_sum`.

### Eager-loading rules

- **Many-to-many collections load with `selectinload`, never `joinedload`.** Joined, SQLite
  materialises the parenthesised association join by scanning the whole association table, so a
  single `get_by_id` cost grew with library size. This covers `Track.artists`, `Track.genres`,
  `Artist.tracks`, `Genre.tracks`, `Playlist.tracks`.
- Many-to-one (`Track.album`, `Album.artist`) may be joined, but paginated or DISTINCT queries
  use `selectinload` so a join cannot multiply rows. `_track_eager_options(collections_via_selectin=...,
  list_read=...)` encodes this; `list_read=True` also defers `lyrics` and `comments`.
- **Define option tuples once at module scope** and reuse them on every read path of that
  entity: `_ALBUM_DETAIL_OPTIONS`, `_ALBUM_LIST_OPTIONS`, `_ARTIST_DETAIL_OPTIONS`,
  `_ARTIST_LIST_OPTIONS`, `_GENRE_LOAD_OPTIONS`, `_PLAYLIST_DETAIL_OPTIONS`. A new read path then
  cannot silently omit a relationship. Entities that hand a collection of tracks to
  `Track.to_dict()` compose `nested_track_options(Parent.tracks)` rather than spelling the chain.
- List reads that only need counts use `with_expression` + `correlated_count` /
  `correlated_sum` instead of loading children.
- **The `refresh()` pitfall.** After `commit()` an instance is expired; `session.refresh(obj)`
  reloads its columns but does **not** re-apply the query's loader options, so relationships stay
  unloaded and raise once the object is expunged. Either touch the relationship while still
  attached (`_ = genre.tracks`, as `GenreRepository.create` does) or re-query with the options
  and expunge the result (`TrackRepository.add` and `_reload_detached` in
  [`track_repository_mutation.py`](../../auralis/library/repositories/track_repository_mutation.py)).
- `IN` queries are batched below SQLite's variable limit (`_iter_in_batches`,
  `_SQLITE_IN_BATCH_SIZE`).

### Identity and concurrency conventions

- **Path identity is `filepath_key`**, from `make_filepath_key()` in
  [`path_key.py`](../../auralis/library/path_key.py): case-folded on Windows and macOS, case
  preserving on Linux, separators normalised. Compare it, never `filepath`, and fill it on every
  write.
- **Get-or-create is `INSERT ... ON CONFLICT DO NOTHING` then re-select**
  (`_get_or_create` in `track_repository_lifecycle.py`), not a SAVEPOINT: pysqlite lets a
  SAVEPOINT commit the transaction, which leaves orphans after a rollback.
- A test that inserts `Artist(name=...)` without `normalized_name` makes `TrackRepository.add()`
  roll back and return `None`; datasets come out silently empty.
- Track deletes go through `delete_tracks_by_ids`, which calls `prune_orphans` in the same
  transaction: albums, artists and genres no track references are removed, and an album's
  artwork file is unlinked only after the commit.

---

## 5. Fingerprints and the similarity graph

`track_fingerprints` and `similarity_graph` hang off `tracks` by foreign key with
`ON DELETE CASCADE`; deleting a track removes both. Which tracks need a fingerprint, how rows are
claimed (a placeholder row with `lufs=-100` marks a claim) and how the KNN graph is built are
owned by [fingerprinting.md](fingerprinting.md) (§5 scheduling, §4 similarity); the library side
is:

- `FingerprintSchedulerRepository` claims atomically through per-queue cursors;
  `FingerprintStatsRepository.cleanup_incomplete_fingerprints` releases abandoned claims.
- `SimilarityGraphRepository.replace_edges` swaps a set of tracks' edges in one transaction and
  skips edges to deleted tracks; `prune_untracked` and `clear_all` maintain it.
- A rescan that finds the **audio changed** deletes the stored fingerprint in the same
  transaction as the update (§7), because the extractor skips tracks that already have a row.
- Per-file `.25d` sidecars (`sidecar_manager.py` and the `sidecar_*` modules) live in this
  package but are documented in [fingerprinting.md §3](fingerprinting.md#3-storage--two-25d-systems).

---

## 6. Migrations

Schema version is `__db_schema_version__` in [`auralis/__version__.py`](../../auralis/__version__.py)
(currently 34). Scripts are `migrations/migration_v<from>_to_v<to>.sql`, one per step, plus
[`migrations/README.md`](../../auralis/library/migrations/README.md). Never edit a released script.

`check_and_migrate_database(db_path, auto_backup=True)`
([`migration_manager.py`](../../auralis/library/migration_manager.py)):

1. Read the current version (`SchemaVersionStoreMixin.get_current_version`: 0 for a fresh file;
   any other read failure raises rather than reading as 0). Equal: done, no lock. Newer than the
   app: return False.
2. Take `migration_lock(db_path)`
   ([`migration_lock.py`](../../auralis/library/migration_lock.py)): a thread lock **and** an
   OS file lock (`fcntl.flock` / `msvcrt`) on `.<db>.migration.lock`, 30 s shared budget. The lock
   file is never deleted (locks bind to the inode). Re-check the version under the lock.
3. For an existing database (`current_version > 0`), `backup_database` writes a consistent
   snapshot with the SQLite Online Backup API (reads through the WAL), mode `0600`. A failed
   backup aborts the migration.
4. `migrate_to_latest`: version 0 runs `initialize_fresh_database` (`create_all` and a version
   row; refuses a file that has tables but no version); otherwise it applies steps one at a time.
5. Each step (`run_migration_step` in
   [`migration_steps.py`](../../auralis/library/migration_steps.py)) validates the SQL
   (`DROP TABLE` only with an `-- @ALLOW_DROP_TABLE` marker; no unqualified `DELETE FROM`), splits
   it with `split_sql_statements` (uses `sqlite3.complete_statement`, so a `;` inside a comment,
   string or trigger does not split), and runs DDL plus the `schema_version` insert in **one**
   transaction on the raw DBAPI connection. Replays of `ADD COLUMN` / `DROP COLUMN` that already
   happened are tolerated.
6. On a failed or raised step, `restore_pre_migration_backup` restores the snapshot under the
   lock; on success `prune_old_backups` keeps the newest `KEEP_PRE_MIGRATION_BACKUPS` (3) files
   named `<stem>.backup_<timestamp><suffix>`.

Adding a migration: bump `__db_schema_version__`, add the next-numbered script, and mirror the
change on the model: a fresh database is built by `create_all` and never runs the scripts. An
index declared on a model after a database was created is added on open by
`create_missing_declared_indexes` ([`schema_indexes.py`](../../auralis/library/schema_indexes.py))
without a version bump.

---

## 7. The scanner

`LibraryScanner(library_database)` ([`scanner/scanner.py`](../../auralis/library/scanner/scanner.py))
is constructed per scan; its pieces are `FileDiscovery`, `AudioAnalyzer`, `MetadataExtractor`
(mutagen) and `BatchProcessor`. It does **not** enqueue fingerprints: the callers
(`routers/library_scan.py`, `LibraryAutoScanner`) do that after the scan returns, using
`ScanResult.added_tracks` and `updated_tracks` (id-only `ScannedTrackRef`s).

`scan_directories(directories, recursive, skip_existing, check_modifications, batch_size)`:

1. `scan_roots` drops duplicate and (when recursive) nested roots. `claim_scan` takes a scan
   slot and reserves the directories; on rejection `result.rejected` is set and nothing is held.
2. **Counting pass** (`count_audio_files`) walks once to fix the progress denominator and caches
   up to 100 000 paths (`_PATH_CACHE_LIMIT`); past that it re-walks rather than grow memory.
3. **Streaming pass:** `BatchFeeder` fills batches of `DEFAULT_BATCH_SIZE` (50) and hands each to
   `BatchProcessor.process_file_batch`, so memory stays bounded for any library size.
4. `finally` releases the paths and slot, then fires `on_scan_complete` (unless rejected).

**Discovery** (`FileDiscovery`): extensions from `auralis.io.formats.AUDIO_EXTENSIONS` (one
source of truth with the loader); hidden and `SKIP_DIRECTORIES` skipped; depth capped at
`MAX_SCAN_DEPTH` (50); directory inodes tracked so circular or duplicate symlinks are walked
once. Symlinked subdirectories are followed with no containment check, by design (a library
spanning volumes is legitimate). Orphaned `.<name>.XXXXXXXX.bak` files from an interrupted tag
edit are reported in `ScanResult.stale_backups`, never deleted.

**Per file** (`BatchProcessor.process_single_file`), after one batched lookup of existing rows
(`tracks.get_by_paths`):

- **Skip:** a known row is skipped when `file_mtime` (the scanner's own watermark, not
  `updated_at`) matches within `MTIME_TOLERANCE_SEC` and the size is equal or unknown. The
  comparison is equality, so a file restored with an *older* mtime counts as changed. A NULL
  watermark means "unknown" and forces one refresh.
- **Update (rescan):** `tracks.update_by_filepath(path, info, replace_tags=True)`. The scan is a
  whole-file read, so a tag that is absent now **is cleared** (artists, genres, album, track /
  disc / year); with `replace_tags` off, absent keys are left alone. The mtime watermark is
  `stat`ed *before* the content is read, so an edit during the read leaves the stored mtime older
  than the file and the next scan re-reads it.
- **Replaced file:** `_audio_changed` (size, duration, sample rate, channels, format, mtime) is
  true when a different recording now sits at the path; the stored fingerprint is deleted in the
  same transaction, because the fingerprint extractor skips any track that already has one.
- **Moved file:** a path new to the library is checked with
  `tracks.relocate_missing_track(path, filesize, duration)`: exactly one existing row with the
  same byte size and a duration within 0.5 s whose own file is *provably* gone (ENOENT or
  ENOTDIR) is re-pointed to the new path, keeping its id, playlists, favourite, play count and
  fingerprint. Zero or several candidates means "not a move" and a new row is added. If the
  check itself raises, the file is reported `unresolved_move` (not added), because adding a twin
  would let the post-scan prune delete the original with its user data.
- **Add:** `tracks.add(info)`; failures carry a path and reason in `ScanResult.failures`
  (bounded; `files_failed` is exact). A file name that is not valid UTF-8 fails with a clear
  reason.

**Pruning missing tracks** happens after the scan, in the callers, and only when
`ScanResult.prune_safe` is true: every folder was read (`walk_complete`: no `directory_errors`,
no `error`) **and** no moved-file check failed. A folder that vanishes or turns unreadable
mid-walk (an unplugged drive, a dropped share, permission denied) is recorded in
`directory_errors`, which disables the prune for that scan so a missing mount cannot delete the
tracks under it. When the prune does run (`services/missing_tracks.py`), `cleanup_missing_files`
deletes a track only if its file is *definitely* missing on two checks (`os.stat` returning
ENOENT/ENOTDIR; any other error means "cannot tell" and skips) and its parent directory still
exists (a gone parent suggests an unmounted volume).

Removing a configured scan folder is separate: `remove_tracks_under_folder(folder,
keep_folders=...)` deletes every track under it without checking the disk (the folder is no
longer a trusted root), but keeps tracks that are also under a still-configured nested folder.

Cancellation is a shared `threading.Event` (`should_stop`) polled by discovery and batch
processing; `stop_scan()` sets it.

---

## 8. Pitfalls

- **Never build a session outside a repository.** Add a repository method instead.
- **Never `joinedload` a many-to-many**, and never add a read path without the module-scope
  option tuple for its entity.
- **Never `refresh()` and then expunge** without touching or re-querying the relationships.
- **Do not compare `filepath` for identity**; use `filepath_key`.
- **Do not hold a repository session across an `await` or an engine lock.** Sessions are
  per call; backend code calls repositories through `asyncio.to_thread`.
- **A migration that needs `DROP TABLE` must carry `-- @ALLOW_DROP_TABLE`**; an unqualified
  `DELETE FROM` is rejected outright.
- **Do not call `cleanup_incomplete_fingerprints()` from a constructor.**
- **Do not "fix" `_guarded` returning `None` on failure** without auditing every caller: the
  not-found / failed ambiguity is part of its contract.
- **Backend tests that boot the app touch the real `~/.auralis/library.db`** unless `HOME` is
  redirected.
- The test `session_factory` fixture (`tests/conftest.py`) builds its own engine without the
  `foreign_keys` pragma, so it does not enforce foreign keys; use a real `LibraryDatabase` on a temp file for FK behaviour.

---

## 9. Where to start reading

1. [`database.py`](../../auralis/library/database.py) and
   [`database_engine.py`](../../auralis/library/database_engine.py): construction and engine.
2. [`repositories/base.py`](../../auralis/library/repositories/base.py) and
   [`repositories/track_repository.py`](../../auralis/library/repositories/track_repository.py):
   session semantics and the eager-load helper.
3. [`models/_helpers.py`](../../auralis/library/models/_helpers.py) and
   [`models/track.py`](../../auralis/library/models/track.py).
4. [`migration_manager.py`](../../auralis/library/migration_manager.py) and
   [`migration_steps.py`](../../auralis/library/migration_steps.py).
5. [`scanner/batch_processor.py`](../../auralis/library/scanner/batch_processor.py) and
   [`repositories/track_repository_relocation.py`](../../auralis/library/repositories/track_repository_relocation.py).
6. [`scan_models.py`](../../auralis/library/scan_models.py): `ScanResult`, `prune_safe`.
7. Tests: [`tests/auralis/library/`](../../tests/auralis/library/).

**Related:** [fingerprinting.md](fingerprinting.md) · [backend-api.md](backend-api.md) ·
[player.md](player.md) · [../development/REPOSITORY_PATTERN.md](../development/REPOSITORY_PATTERN.md) ·
[../architecture/data-flow.md](../architecture/data-flow.md)
