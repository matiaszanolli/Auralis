# Frontend Integration Tests

## History

`#5119` found that most of this tree — 14 files here plus
`../api-integration/library-api.test.ts` (15 total) — imported zero production
modules. Each one defined a throwaway React component inside the test file
(`SearchableLibrary`, `CachedLibrary`, `VirtualList`, `TestAPIComponent`, …)
and asserted against that fixture instead of the app. They ran green in every
CI pass while testing nothing; deleting the feature a file named would have
left every test in it green. `#5119` wrapped them in `describe.skip`, with a
per-file docstring naming where real coverage for that area actually lived,
as a starting point for a follow-up — the same fix `#3935` had already applied
to one file in this tree (`streaming-audio/streaming-mse.test.tsx`, later
deleted outright by `#4399` once its feature, MSE, was confirmed unused).

`#5186` is that follow-up. Every one of the 14 remaining files' own docstring
already pointed at real, existing coverage elsewhere — verified true (not just
trusted) before acting — so all 14 were **retired** (deleted), not rewritten:
duplicating already-covered ground as a brand-new integration suite would have
added maintenance cost and flake risk without closing an actual coverage gap.
The retired files, and where their area is covered instead, are listed below.
`integration-tests-exercise-production-code.test.ts` (the `#5119` guard) still
runs — it requires every remaining spec in this tree and in
`../api-integration/` to import at least one production module or be
explicitly skipped with a reason, so a new fixture-only suite fails immediately
rather than sitting green for another year.

## What's here now

```
tests/integration/
├── library-management/
│   ├── library-management.test.tsx   # renders the real CozyLibraryView
│   └── playlist-management.test.tsx  # renders the real PlaylistList + playlistService
└── websocket-realtime/
    └── websocket-realtime.test.tsx   # vi.unmock()s the real WebSocketContext
```

All three exercise real production code and are the reference pattern for any
future integration spec in this tree.

## Retired by #5186 (2026-09-14) — real coverage lives elsewhere

| Retired file | Real coverage now |
|---|---|
| `library-management/search.test.tsx` | `src/hooks/library/__tests__/useLibraryQuery.test.ts` + the `CozyLibraryView` specs |
| `library-management/filter.test.tsx` | the `CozyLibraryView` / track-list specs |
| `library-management/sort.test.tsx` | the `CozyLibraryView` / track-list specs |
| `library-management/metadata.test.tsx` | `src/components/library/EditMetadataDialog/__tests__/useMetadataForm.test.ts` |
| `library-management/artwork.test.tsx` | `src/components/shared/MediaCard/__tests__/` + `src/services/__tests__/artworkService.test.ts` |
| `library-management/accessibility.test.tsx` | the co-located component a11y specs (e.g. `src/components/core/__tests__/singleH1PerView.test.tsx`) |
| `performance/cache-efficiency.test.tsx` | the React Query cache behaviour exercised by the real library hook specs |
| `performance/memory-management.test.tsx` | the per-hook cleanup assertions in the real hook specs |
| `performance/pagination.test.tsx` | `src/hooks/library/__tests__/useLibraryPagination.test.ts` + `useInfiniteAlbums.test.ts` |
| `performance/virtual-scrolling.test.tsx` | `CozyAlbumGrid.test.tsx`, `TrackGridView.test.tsx`, `ArtistListContent.test.tsx` |
| `performance/performance-large-libraries.test.tsx` | the same real virtualization specs as above |
| `performance/bundle-size.test.tsx` | nowhere — bundle composition is a build concern, not a unit-test one (see `#4697`); the file asserted on `React.lazy`/object-literal behavior unrelated to Auralis's own code |
| `error-handling/error-handling.test.tsx` | `src/utils/httpError.ts`'s consumers (`src/types/__tests__/apiErrorHandler.test.ts`, `src/hooks/player/__tests__/usePlayTrack.test.ts`) and the other per-hook error-path specs |
| `../api-integration/library-api.test.ts` | `src/services/__tests__/libraryService.test.ts` + the library hook specs |

`streaming-audio/streaming-mse.test.tsx` (`#3935`) was already retired earlier
(commit `56142bca`, `#4399`) — listed here only because this README used to
still describe it as present.

`package.json`'s per-file/per-directory npm scripts for the retired files
(`test:player`, `test:streaming`, `test:enhancement`, `test:errors`,
`test:performance`, `test:pagination`, `test:virtual-scrolling`, `test:cache`,
`test:bundle`, `test:memory-mgmt`, `test:search`, `test:filter`, `test:sort`,
`test:accessibility`) were removed in the same change — several already
pointed at directories (`player-controls/`, `streaming-audio/`,
`enhancement-processing/`) that had been reorganized away before this cleanup
and were already dead. `test:library`, `test:websocket` and `test:integration`
remain valid and unchanged.

## Running the remaining tests

```bash
npm run test:library       # library-management/
npm run test:websocket     # websocket-realtime/
npm run test:integration   # this whole tree
```

## Adding a new integration spec here

Follow the pattern in `library-management/library-management.test.tsx` or
`websocket-realtime/websocket-realtime.test.tsx`: render the real production
component/hook (via `render()` from `@/test/test-utils`, which wires the
required providers), exercise it against MSW-mocked API responses, and assert
on what the user would actually see. The guard test
(`integration-tests-exercise-production-code.test.ts`) will fail the suite if
a new spec imports no production module and isn't explicitly `describe.skip`
with a reason.

## Related Documentation

- [TESTING_GUIDELINES.md](../../../docs/development/TESTING_GUIDELINES.md) — test quality standards
- [src/test/test-utils.tsx](../../test/test-utils.tsx) — custom render & provider setup
- [src/test/mocks/](../../test/mocks/) — MSW handlers and mock data
