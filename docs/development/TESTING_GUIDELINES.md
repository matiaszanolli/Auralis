# Testing Guidelines

How to write a test in this repository. Mandatory reading for contributors. How to run the
suites, what CI gates, and how the failure baselines work are in
[TEST_EXECUTION_GUIDE.md](TEST_EXECUTION_GUIDE.md); the rules behind the weak-test gates are
in [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md).

## Philosophy

A test earns its place by being able to fail when the code is wrong. Coverage measures which
lines ran, not whether anything checked the result, so a green test with full coverage can
still pin nothing. The rules below follow from that.

1. **Assert the value the test is named for.** `assert processor is not None` passes against
   almost any defect. A test named for a count asserts the count; a test named for a payload
   asserts the payload's fields.
2. **Test properties that must hold, not the implementation.** Assert what the system does
   (output length equals input length, every item is returned exactly once), not that a private
   method was called. A test that patches the function it exercises tests the patch.
3. **Use the real constants and counters.** Chunk geometry comes from
   `auralis-web/backend/core/chunk_boundaries.py` (`CHUNK_DURATION`, `OVERLAP_DURATION`,
   `content_chunk_count()`); a test that restates `ceil(duration / 15)` re-derives the bug it
   should catch.
4. **Prove the test can fail.** Before trusting a new test, break the code it guards (flip the
   constant, return the wrong value) and watch it fail. A regression test is written to fail
   first against the unfixed code.
5. **No conditional assertions.** An `assert` inside an `if` with no `else` checks nothing when
   the condition is false. Look the element or record up unconditionally and assert on it.
6. **No test without an assertion.** A print-only test, or one that ends in a comment such as
   "documents expected behaviour", is green against every defect.
7. **Deterministic.** Seed random generators (`np.random.default_rng(0)`), do not sleep to wait
   for a thread (wait on an event with a timeout), and do not touch the network or the user's
   library.

Two ratchet gates enforce rules 1 and 6 mechanically (`scripts/check_weak_assertions.py` and,
for the frontend, `scripts/check-weak-tests.mjs`); see
[DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md#tests-as-a-standard). A new offender fails
CI. `tests/conftest.py` also warns at collection time about a new `is not None`-only test.

### Example: assert a property, with a message that names the defect

```python
# tests/auralis/test_audio_processing_invariants.py
@pytest.mark.audio
@pytest.mark.integration
def test_processing_preserves_sample_count_mono(processor, test_audio_mono):
    audio, sr = test_audio_mono
    processed = processor.process(audio)

    assert len(processed) == len(audio), (
        f"Sample count changed during processing: "
        f"input={len(audio)}, output={len(processed)}"
    )
```

### Example: boundary test against the real counter

```python
# tests/boundaries/test_chunked_processing_boundaries.py
def test_audio_exactly_one_chunk_duration(temp_audio_dir):
    ...
    assert processor.total_chunks == content_chunk_count(duration), (
        f"Audio of exactly {CHUNK_DURATION}s should create 1 chunk, "
        f"got {processor.total_chunks}"
    )
```

## Where tests live

| Directory | Holds |
|-----------|-------|
| `tests/auralis/` | Engine tests, mirroring the `auralis/` package tree (`analysis/`, `core/`, `dsp/`, `io/`, `library/`, `player/`, `services/`, ...). Cross-cutting invariants such as `test_audio_processing_invariants.py` sit at the top. |
| `tests/backend/` | Routers, services, WebSocket handlers, the chunked processor. Most files boot `main.app` through the `client` fixture. |
| `tests/integration/` | Cross-component and end-to-end flows. |
| `tests/boundaries/` | Edge-of-range behaviour: empty, single item, exact boundary, extreme value. |
| `tests/regression/` | One file per fixed bug, plus tests of the CI scripts themselves (`test_check_*`). |
| `tests/security/`, `tests/concurrency/`, `tests/edge_cases/` | By concern. |
| `tests/vendor/` | The Rust DSP module through PyO3. |
| `tests/performance/`, `tests/load_stress/`, `tests/stress/` | Large-library and load runs; every test in them is marked `slow` and runs nightly. |
| `auralis-web/frontend/src/**/__tests__/` | Frontend tests, colocated with the source as `*.test.ts(x)`. |

A regression test is named for the subject and the issue it pins, `test_<subject>_<NNNN>.py`,
and states in its module docstring what was wrong. Declare any new marker in `pytest.ini`
(`--strict-markers` is on). Mark a test `slow` only when it genuinely exceeds a few seconds;
the nightly job is the only place it runs.

## Python fixtures

Shared fixtures are in `tests/conftest.py`; the backend adds more in `tests/backend/conftest.py`.
Run `python -m pytest --fixtures tests/backend/test_albums_api.py` to list what a file can see.

### Audio

| Fixture | Gives |
|---------|-------|
| `temp_dir` | Session-scoped temporary `Path`. |
| `sine_wave`, `white_noise` | Factory callables: `audio, sr = sine_wave(duration=1.0, sample_rate=44100, stereo=True)`; float32, shape `(samples, channels)`. `white_noise` is unseeded; seed NumPy yourself when the value matters. |
| `test_audio_files` | Dict of name to WAV path (`quiet_target.wav`, `loud_reference.wav`, `bass_heavy.wav`, `treble_heavy.wav`, `short_audio.wav`, `long_audio.wav`, `hires_audio.wav`). |
| `audio_pair` | `(target, reference, sample_rate)`, quiet and loud. |
| `sample_rates`, `bit_depths` | Lists for parametrisation. |

`assert_audio_equal` and `assert_rms_similar` (module-level helpers in `tests/conftest.py`)
compare arrays with a tolerance and report the difference.

### Library

| Fixture | Gives |
|---------|-------|
| `temp_test_db` | `(db_path, temp_dir)` for a throwaway database file. |
| `library_database` | A `LibraryDatabase` on that file (engine with foreign keys on, repository properties such as `.tracks`). |
| `session_factory` | A SQLAlchemy `sessionmaker` on the same file, migrated to the current schema. Raw engine: **foreign keys are not enforced.** |
| `repository_factory` | `RepositoryFactory(session_factory)`. |
| `track_repository`, `album_repository`, `artist_repository`, `genre_repository`, `playlist_repository`, `fingerprint_repository`, `stats_repository`, `settings_repository` | One repository from the factory. |
| `get_repository_factory_callable` | A callable returning the factory, for components that take one by injection. |
| `dual_mode_data_source` | Parametrised over `library_database` and `repository_factory`. |
| `temp_library`, `sample_audio_file` | `(LibraryDatabase, audio_dir, temp_dir)` and a 3 s stereo WAV in that directory, for end-to-end flows. |

Rules that bite:

- **Foreign keys are off on `session_factory` and everything built on it**
  (`repository_factory`, `*_repository`). An orphaned `album_id` or a delete that should cascade
  succeeds silently there. A test about referential integrity or cascade must use
  `library_database`, whose engine sets `PRAGMA foreign_keys=ON`.
- **Seed through the repository, not through raw ORM rows.** `track_repository.add({...,
  'artists': ['Name'], 'album': 'Title'})` resolves or creates the artist and album with their
  `normalized_name`. A test that inserts `Artist(name=...)` directly without `normalized_name`
  makes a later `TrackRepository.add()` for that artist roll back and return `None`, so the
  dataset comes out silently empty. When a test must build ORM rows, set it:
  `Artist(name="Queen", normalized_name="queen")`. Assert `add()` did not return `None`.
- **Repositories return detached instances.** A relationship the query did not eager-load raises
  `DetachedInstanceError` (or, through `to_dict()`, logs a warning and degrades to `[]`). Test
  the payload a caller sees, not only that the call returned.
- `session_factory` and `library_database` may be requested in the same test; they share one
  migrated file.
- Do not call repository methods on the class (`TrackRepository.add(...)`); build the repository
  through the factory.

```python
# tests/backend/test_track_list_payload_5906.py
def _seed(track_repository) -> int:
    track = track_repository.add({
        'title': 'Lyric Track', 'filepath': '/tmp/lyric_track_5906.wav',
        'duration': 100.0, 'sample_rate': 44100, 'channels': 2, 'format': 'WAV',
        'artists': ['Lyric Artist'], 'album': 'Lyric Album',
    })
    assert track is not None
    return track.id
```

### Backend API

| Fixture | Gives |
|---------|-------|
| `client` | A `TestClient(main.app)` with the real lifespan, a throwaway library database, a valid `Origin` header on HTTP and WebSocket requests, and the rate limiter reset per test. |
| `library_track`, `sample_track_ids` | Tracks inserted through `client`. |
| `mock_track`, `mock_library_database`, `mock_repository_factory`, `mock_track_repository`, `mock_album_repository`, `mock_artist_repository` | `Mock`-based doubles for router tests that should not touch a database. |
| `reset_rate_limits` | Callable that clears the rate-limit budget mid-test, for a test that loops one route. |

Isolation matters because booting the app opens the library, migrates it, writes a backup beside
it, and starts background workers; a library reset or Clear Cache also sweeps the central `.25d`
fingerprint store.

- `client` requests `_isolated_library_db`, and `tests/backend/conftest.py` and
  `tests/integration/conftest.py` apply `_isolated_fingerprint_store` automatically. Both are
  defined in `tests/app_isolation.py` and are available from any directory.
- A test that boots `main.app` another way (its own `TestClient(app)`, `lifespan`) must request
  both fixtures. `tests/integration/test_app_isolation_6441.py` shows the check.
- When unsure whether a test reaches the real `~/.auralis`, run it with a scratch home:
  `HOME=$(mktemp -d) python -m pytest ...`.
- Use `client` for an endpoint's HTTP contract; use the `mock_*` fixtures or a repository-backed
  fixture to test a handler's logic in isolation. A mock of the repository cannot fail on a
  query bug, so do not use one to test a query.

### Rust DSP

Tests that call `auralis_dsp` (everything in `tests/vendor/`, the fingerprint tests) need the
module built (`maturin develop`) and must run without a `ulimit -v` cap, because rayon cannot
reserve thread stacks under one and the failure looks like a DSP panic. Guard an optional
dependency with `pytest.importorskip("auralis_dsp")` only when the test is truly independent of
it; a skip is invisible in CI.

## Test kinds

**Invariant tests** assert a property over inputs: sample count preserved, no NaN or Inf, output
dtype float32 or float64, input array not modified, position never past duration. Use real
audio (the `sine_wave` fixture, a synthetic stereo signal), vary length and channel count with
`@pytest.mark.parametrize`, and assert on the processed output, not on a mock.

**Boundary tests** probe the edges the code branches on: empty collection, single item, exactly
one chunk, one sample over and under a chunk boundary, `offset == total`, `limit == 0`,
maximum and minimum values. `tests/boundaries/` is the model. Pagination boundaries assert the
union of pages equals the collection with no duplicates and no gaps.

**Integration tests** run several real components together (scan to database to API;
player to queue to gapless engine). Stub only the process boundary (decoder, network), not the
repositories.

**Failure tests** assert the failure mode, not just that something was raised: the HTTP status
and body, the typed error code, that nothing was partially written, that a timeout leaves the
system usable. Use `pytest.raises(..., match=...)` and assert on the log record or response
body.

**Concurrency tests** use real threads or processes and bound every wait.
`tests/concurrency/helpers.py` (`run_concurrent`, `run_concurrent_with_barrier`) take a
`timeout`, join with a deadline, and mark threads `daemon=True`; an unbounded
`Barrier.wait()` or a `join()` whose result is never checked can hang the whole run when one
thread fails to start. Use `multiprocessing.Process` plus a `Queue` when the test needs true
parallelism.

**Performance and memory tests** live under `tests/performance/`, `tests/load_stress/` and
`tests/stress/` (nightly). Assert a budget with headroom for a shared CI runner, and record
what was measured in the failure message.

## Frontend tests

Vitest with jsdom and React Testing Library; `describe` / `it` / `expect` / `vi` are globals.
`src/test/setup.ts` runs for every file.

- Import `render`, `screen` and the rest from `@/test/test-utils`, not from
  `@testing-library/react`. Its `render` wraps the component in the Redux store, React Query,
  theme, toast and playback-session providers; `createTestStore(preloadedState)` seeds
  player and queue state without dispatching.
- `WebSocketContext` is mocked globally in `setup.ts`. A spec that needs the real one calls
  `vi.unmock('../contexts/WebSocketContext')` (see
  `src/contexts/__tests__/WebSocketContext.audioChunk.test.tsx`). Do not build a second private
  mock provider.
- REST calls are answered by MSW (`src/test/mocks/handlers.ts`, fixtures in
  `src/test/mocks/mockData.ts`, the single source of fixture data). Override per test with
  `server.use(http.get(...))`. A request to `/api/` that no handler answers fails the test in
  `afterEach`, because a hook that swallows a network failure otherwise passes against a backend
  that never answered. A spec that deliberately drives unanswered requests clears
  `unhandledApiRequests` in its own `afterEach`.
- Assert on rendered output and user-visible behaviour: query by role or text, drive with
  `userEvent`, and wait with `findBy*` / `waitFor`. Do not assert on component state or on a
  mock's call count unless the call is the behaviour (a request sent, a WebSocket message).
- A spec needs an assertion that can fail: not only `toBeDefined`, `toBeTruthy`,
  `not.toBeNull`, `not.toBeUndefined`, and no assertion inside an `if` without an `else`
  (`pnpm run test:weak`).
- `vi.mock` targets must exist; `src/tests/vi-mock-targets-exist.test.ts` fails on a mock of a
  deleted module.
- `pnpm run type-check` includes test files, so a fixture whose shape drifts from the production
  type fails CI.
- After deleting components or styles, also run `pnpm exec vitest run src/design-system`:
  `unreadTokens.test.ts` fails on a design token nothing reads.
- Scope runs to what you changed and use the 2 GB-heap scripts (see
  [TEST_EXECUTION_GUIDE.md](TEST_EXECUTION_GUIDE.md#frontend-tests)).

Worked examples: `src/components/player/__tests__/PlayerTickMemoization.test.tsx` seeds the store
with `preloadedState: { player: { currentTrack, volume, isMuted } }`, and
`src/test/__tests__/mswUnhandled.5681.test.ts` covers the unhandled-request failure.
`src/test/README.md` has the quick start.

## Pitfalls

- **Testing the mock.** If every collaborator is a `Mock`, the test passes whatever the code
  does. Mock the process boundary and keep the logic real.
- **Weak oracle.** `len(result) >= 0`, `assert True`, `x or True`, `is not None` as the only
  check. Assert the expected value.
- **Silent empty datasets.** A loop over zero rows asserts nothing. Assert the dataset size
  before iterating over it.
- **Time and order dependence.** `time.sleep` to wait for a worker, tests that need another test's
  leftovers, assertions on dict or set ordering. Fix the ordering explicitly.
- **Shared state.** The rate limiter, the rejection-log throttle and the converted-WAV
  retention are process-wide; the backend conftest resets them per test. Reset any new global
  the same way, in a fixture, not in the test body.
- **Ignoring a failure.** Do not add a failing test to a baseline or mark it `xfail` to get
  green. Fix it; the baselines only shrink.
- **Hardcoded paths and counts.** Use `tmp_path` / `temp_dir` for files and compute
  expected counts from the production constant.

## Coverage

Run `pytest --cov=auralis` to find untested branches. No threshold is enforced, and the
number is a map of what to look at next, not a quality measure: a line can be covered by a test
that checks nothing. Judge a test by what it would catch.
