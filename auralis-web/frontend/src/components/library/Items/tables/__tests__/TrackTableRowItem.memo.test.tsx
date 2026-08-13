/**
 * Track-row memoization (#4472)
 *
 * `AlbumTrackTable` reads playback state from Redux, so every play/pause tick
 * re-renders it and — before these components were wrapped in `React.memo` —
 * all 20-30 of its rows with it. The rows take `isPlaying` but only ever read
 * it as `isCurrentTrack && isPlaying`, so a toggle cannot change what a
 * non-current row renders; the comparator encodes that, and these tests pin it.
 *
 * Render counts are taken from a spy threaded through a prop that the
 * comparator treats as stable (`formatDuration`), so the count reflects the
 * component body actually running.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@/test/test-utils';
import { TrackTableRowItem } from '../TrackTableRowItem';
import { ArtistTrackRow } from '@/components/library/Views/ArtistTrackRow';
import type { DetailTrack } from '@/types/domain';

const track = (id: number): DetailTrack => ({
  id,
  title: `Track ${id}`,
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 200,
  filepath: `/music/${id}.flac`,
} as DetailTrack);

const trackA = track(1);
const trackB = track(2);

/** Counts body executions: each row calls formatDuration once while rendering. */
function makeRenderCounter() {
  const formatDuration = vi.fn((seconds: number) => `0:${seconds}`);
  return {
    formatDuration,
    calls: () => formatDuration.mock.calls.length,
  };
}

describe('TrackTableRowItem memoization (#4472)', () => {
  let onTrackClick: (t: DetailTrack) => void;
  let onFindSimilar: (id: number) => void;
  let counter: ReturnType<typeof makeRenderCounter>;

  const renderTable = (isPlaying: boolean, currentTrackId: number | null) =>
    render(
      <table>
        <tbody>
          {[trackA, trackB].map((t, index) => (
            <TrackTableRowItem
              key={t.id}
              track={t}
              index={index}
              isCurrentTrack={currentTrackId === t.id}
              isPlaying={isPlaying}
              onTrackClick={onTrackClick}
              onFindSimilar={onFindSimilar}
              formatDuration={counter.formatDuration}
            />
          ))}
        </tbody>
      </table>
    );

  beforeEach(() => {
    onTrackClick = vi.fn();
    onFindSimilar = vi.fn();
    counter = makeRenderCounter();
  });

  it('does not re-render rows when a play/pause tick leaves their output unchanged', () => {
    const { rerender } = renderTable(false, null);
    const afterFirstRender = counter.calls();
    expect(afterFirstRender).toBe(2); // both rows rendered once

    // The play/pause tick: isPlaying flips for every row, no row is current.
    rerender(
      <table>
        <tbody>
          {[trackA, trackB].map((t, index) => (
            <TrackTableRowItem
              key={t.id}
              track={t}
              index={index}
              isCurrentTrack={false}
              isPlaying
              onTrackClick={onTrackClick}
              onFindSimilar={onFindSimilar}
              formatDuration={counter.formatDuration}
            />
          ))}
        </tbody>
      </table>
    );

    expect(counter.calls()).toBe(afterFirstRender);
  });

  it('does re-render the current track when playback pauses', () => {
    const { rerender } = renderTable(true, trackA.id);
    const afterFirstRender = counter.calls();

    rerender(
      <table>
        <tbody>
          {[trackA, trackB].map((t, index) => (
            <TrackTableRowItem
              key={t.id}
              track={t}
              index={index}
              isCurrentTrack={trackA.id === t.id}
              isPlaying={false}
              onTrackClick={onTrackClick}
              onFindSimilar={onFindSimilar}
              formatDuration={counter.formatDuration}
            />
          ))}
        </tbody>
      </table>
    );

    // Exactly one extra body run: the current row. The other row is unaffected.
    expect(counter.calls()).toBe(afterFirstRender + 1);
  });

  it('re-renders a row that becomes the current track', () => {
    const { rerender } = renderTable(true, trackA.id);
    const afterFirstRender = counter.calls();

    rerender(
      <table>
        <tbody>
          {[trackA, trackB].map((t, index) => (
            <TrackTableRowItem
              key={t.id}
              track={t}
              index={index}
              isCurrentTrack={trackB.id === t.id}
              isPlaying
              onTrackClick={onTrackClick}
              onFindSimilar={onFindSimilar}
              formatDuration={counter.formatDuration}
            />
          ))}
        </tbody>
      </table>
    );

    // Both rows changed isCurrentTrack, so both re-render.
    expect(counter.calls()).toBe(afterFirstRender + 2);
  });

  it('re-renders when the track object itself changes', () => {
    const { rerender } = renderTable(false, null);
    const afterFirstRender = counter.calls();

    const renamed = { ...trackA, title: 'Renamed' };
    rerender(
      <table>
        <tbody>
          {[renamed, trackB].map((t, index) => (
            <TrackTableRowItem
              key={t.id}
              track={t}
              index={index}
              isCurrentTrack={false}
              isPlaying={false}
              onTrackClick={onTrackClick}
              onFindSimilar={onFindSimilar}
              formatDuration={counter.formatDuration}
            />
          ))}
        </tbody>
      </table>
    );

    expect(counter.calls()).toBe(afterFirstRender + 1);
  });
});

describe('ArtistTrackRow memoization (#4472)', () => {
  it('does not re-render on a play/pause tick when no row is current', () => {
    const onTrackClick = vi.fn();
    const counter = makeRenderCounter();

    const rows = (isPlaying: boolean) => (
      <table>
        <tbody>
          {[trackA, trackB].map((t, index) => (
            <ArtistTrackRow
              key={t.id}
              track={t}
              index={index}
              isCurrentTrack={false}
              isPlaying={isPlaying}
              onTrackClick={onTrackClick}
              formatDuration={counter.formatDuration}
            />
          ))}
        </tbody>
      </table>
    );

    const { rerender } = render(rows(false));
    const afterFirstRender = counter.calls();
    expect(afterFirstRender).toBe(2);

    rerender(rows(true));

    expect(counter.calls()).toBe(afterFirstRender);
  });
});
