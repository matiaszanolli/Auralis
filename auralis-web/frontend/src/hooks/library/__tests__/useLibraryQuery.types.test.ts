/**
 * The library query hooks' item type follows the query type (#6054).
 *
 * `useLibraryQuery<T>(queryType)` used to take the item type and the query type
 * as independent parameters, so `useLibraryQuery<Album>('tracks')` compiled and
 * returned `Track[]` typed as `Album[]`. These are compile-time assertions:
 * `tsc` (pnpm run type-check) fails on a missing or unused `@ts-expect-error`,
 * and `expectTypeOf` is a no-op at runtime.
 */

import { describe, it, expectTypeOf } from 'vitest';
import type { Track, Album, Artist } from '@/types/domain';
import { extractItemsFromResponse } from '../libraryQueryRequest';
import type { UseLibraryQueryResult } from '../libraryQueryTypes';
import { useLibraryQuery } from '../useLibraryQuery';
import { useInfiniteScroll } from '../useLibraryQueries';

describe('library query result types follow the query type (#6054)', () => {
  it('useLibraryQuery yields the item type of its query type', () => {
    // Never invoked: hooks may only run inside a component, and only the types matter here.
    const typeChecks = () => {
      expectTypeOf(useLibraryQuery('tracks').data).toEqualTypeOf<Track[]>();
      expectTypeOf(useLibraryQuery('albums').data).toEqualTypeOf<Album[]>();
      expectTypeOf(useLibraryQuery('artists')).toEqualTypeOf<UseLibraryQueryResult<Artist>>();
      expectTypeOf(useInfiniteScroll('albums').items).toEqualTypeOf<Album[]>();
    };
    void typeChecks;
  });

  it('extractItemsFromResponse needs no caller-supplied item type', () => {
    expectTypeOf(extractItemsFromResponse({}, 'albums')).toEqualTypeOf<Album[]>();
    expectTypeOf(extractItemsFromResponse({}, 'artists')).toEqualTypeOf<Artist[]>();
  });

  it('a mismatched pairing of item type and query type does not compile', () => {
    const typeChecks = () => {
      // @ts-expect-error -- 'Album' is not a query type; the old `useLibraryQuery<Album>('tracks')` shape
      useLibraryQuery<Album>('tracks');
      // @ts-expect-error -- a Track[] result is not an Album[] result
      const albums: Album[] = useLibraryQuery('tracks').data;
      void albums;
    };
    void typeChecks;
  });
});
