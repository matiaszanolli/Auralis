/**
 * Track row menu shows only items that do something (#5614)
 *
 * The songs list never passes Favourite / Go to Album / Go to Artist / Track
 * Info handlers to the row, and the menu used to render them anyway with a
 * no-op handler. Whatever the menu renders must now invoke a real handler.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import TrackRow from '../TrackRow';
import type { LibraryTrack } from '@/types/domain';

vi.mock('@/components/shared/Toast', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/components/shared/Toast')>()),
  useToast: () => ({ success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));

vi.mock('@/services/queueService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/queueService')>()),
  addTrackToQueue: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('@/services/playlistService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/playlistService')>()),
  getPlaylists: vi.fn().mockResolvedValue({ playlists: [], total: 0 }),
}));

const track = {
  id: 7,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  albumId: 3,
  duration: 180,
} as LibraryTrack;

async function openMenu() {
  await userEvent.click(screen.getByRole('button', { name: 'More options for Test Track' }));
  return screen.getByRole('menu');
}

const labels = () => screen.getAllByRole('menuitem').map((item) => item.textContent);

describe('TrackRow context menu items', () => {
  it('lists only the items whose handlers the row was given', async () => {
    render(<TrackRow track={track} index={0} onPlay={vi.fn()} onFindSimilar={vi.fn()} />);

    await openMenu();

    expect(labels()).toEqual(expect.arrayContaining(['Play Now', 'Add to Queue', 'Find Similar Tracks']));
    for (const dead of ['Add to Favourites', 'Go to Album', 'Go to Artist', 'Track Info', 'Edit Metadata']) {
      expect(labels()).not.toContain(dead);
    }
  });

  it('shows Favourite, Go to Album and Go to Artist once their handlers are supplied, and calls them', async () => {
    const onToggleFavorite = vi.fn();
    const onShowAlbum = vi.fn();
    const onShowArtist = vi.fn();
    render(
      <TrackRow
        track={track}
        index={0}
        onPlay={vi.fn()}
        onToggleFavorite={onToggleFavorite}
        onShowAlbum={onShowAlbum}
        onShowArtist={onShowArtist}
      />
    );

    await openMenu();
    await userEvent.click(screen.getByRole('menuitem', { name: 'Go to Album' }));
    expect(onShowAlbum).toHaveBeenCalledWith(3);

    await openMenu();
    await userEvent.click(screen.getByRole('menuitem', { name: 'Go to Artist' }));
    expect(onShowArtist).toHaveBeenCalledWith('Test Artist');

    await openMenu();
    await userEvent.click(screen.getByRole('menuitem', { name: 'Add to Favourites' }));
    expect(onToggleFavorite).toHaveBeenCalledWith(7);
  });

  it('hides Go to Album for a track with no album id even when a handler exists', async () => {
    render(
      <TrackRow
        track={{ ...track, albumId: undefined } as LibraryTrack}
        index={0}
        onPlay={vi.fn()}
        onShowAlbum={vi.fn()}
      />
    );

    await openMenu();

    expect(labels()).not.toContain('Go to Album');
  });

  it('does not list a bare Add to Playlist item above the playlist section', async () => {
    render(<TrackRow track={track} index={0} onPlay={vi.fn()} />);

    await openMenu();

    expect(labels().filter((label) => label === 'Add to Playlist')).toHaveLength(1);
  });
});
