/**
 * TracksTab hands isPlaying only to the current track's row (#6023)
 *
 * It passed the global isPlaying boolean to every ArtistTrackRow. A row reads it only when it is
 * the current track, but the prop flipped on all rows at every play/pause, so memo was defeated for
 * the whole artist's track list.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@/test/test-utils';

const { rows, playback } = vi.hoisted(() => ({
  rows: [] as Array<{ id: number; isCurrentTrack: boolean; isPlaying: boolean }>,
  playback: { currentTrackId: 2, isPlaying: true },
}));

vi.mock('../ArtistTrackRow', () => ({
  default: (props: { track: { id: number }; isCurrentTrack: boolean; isPlaying: boolean }) => {
    rows.push({ id: props.track.id, isCurrentTrack: props.isCurrentTrack, isPlaying: props.isPlaying });
    return null;
  },
}));
vi.mock('@/components/library/usePlaybackState', () => ({ usePlaybackState: () => playback }));

import TracksTab from '../TracksTab';

const tracks = [1, 2, 3].map((id) => ({ id, title: `T${id}`, duration: 100 })) as never[];

describe('TracksTab isPlaying fan-out (#6023)', () => {
  beforeEach(() => {
    rows.length = 0;
    playback.currentTrackId = 2;
    playback.isPlaying = true;
  });

  it('only the current track receives isPlaying=true', () => {
    render(<TracksTab tracks={tracks} onTrackClick={vi.fn()} />);

    expect(rows).toEqual([
      { id: 1, isCurrentTrack: false, isPlaying: false },
      { id: 2, isCurrentTrack: true, isPlaying: true },
      { id: 3, isCurrentTrack: false, isPlaying: false },
    ]);
  });

  it('a paused current track receives false', () => {
    playback.isPlaying = false;

    render(<TracksTab tracks={tracks} onTrackClick={vi.fn()} />);

    expect(rows.every((row) => row.isPlaying === false)).toBe(true);
  });
});
