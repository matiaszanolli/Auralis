/**
 * WIRING (#6581): the artist list and the track list own their state, so each resyncs itself on
 * reconnect, through the shared hook rather than another hand-rolled connection watcher.
 */
import { describe, it, expect } from 'vitest';

const sources = import.meta.glob(
  ['/src/components/library/Items/artists/CozyArtistList.tsx', '/src/hooks/library/useLibraryWithStats.ts', '/src/hooks/library/useLibraryChangeSync.ts'],
  { query: '?raw', import: 'default', eager: true }
) as Record<string, string>;

describe('reconnect resync wiring (#6581)', () => {
  it.each(Object.keys(sources))('%s resyncs through useReconnected', (path) => {
    expect(sources[path]).toMatch(/useReconnected\(\w+\)/);
  });

  it('covers the three library consumers', () => {
    expect(Object.keys(sources)).toHaveLength(3);
  });
});
