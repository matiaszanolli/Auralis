/**
 * Track context menu loads the user's playlists (#5617)
 *
 * Both track-row call sites handed ContextMenu an empty `onPlaylistsLoad`, so
 * `playlists` stayed [] and "Add to Playlist" offered only "Create New
 * Playlist". They now pass the hook's stable `fetchPlaylists`: one fetch per
 * menu open, and no refetch loop when the row re-renders while it is open.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import TrackRow from '../TrackRow';
import { TrackTableRowItem } from '@/components/library/Items/tables/TrackTableRowItem';
import * as playlistService from '@/services/playlistService';
import type { DetailTrack, LibraryTrack } from '@/types/domain';

vi.mock('@/services/playlistService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/playlistService')>()),
  getPlaylists: vi.fn(),
}));

vi.mock('@/components/shared/Toast', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/components/shared/Toast')>()),
  useToast: () => ({ success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));

const track = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
} as LibraryTrack & DetailTrack;

const playlists = [
  { id: 10, name: 'Road Trip', track_count: 3 },
  { id: 11, name: 'Focus', track_count: 5 },
] as playlistService.Playlist[];

const formatDuration = (seconds: number) => `${seconds}s`;

const getPlaylists = vi.mocked(playlistService.getPlaylists);

beforeEach(() => {
  getPlaylists.mockReset();
  getPlaylists.mockResolvedValue({ playlists, total: playlists.length } as Awaited<
    ReturnType<typeof playlistService.getPlaylists>
  >);
});

async function openMenu() {
  await userEvent.click(screen.getByRole('button', { name: 'More options for Test Track' }));
  expect(screen.getByRole('menu')).toBeInTheDocument();
}

describe('TrackRow context menu', () => {
  it('fetches playlists once when opened and lists them', async () => {
    render(<TrackRow track={track} index={0} onPlay={vi.fn()} />);

    await openMenu();

    expect(await screen.findByText(/Road Trip/)).toBeInTheDocument();
    expect(screen.getByText(/Focus/)).toBeInTheDocument();
    expect(getPlaylists).toHaveBeenCalledTimes(1);
  });

  it('does not refetch when the row re-renders while the menu is open', async () => {
    const { rerender } = render(<TrackRow track={track} index={0} onPlay={vi.fn()} />);
    await openMenu();
    await screen.findByText(/Road Trip/);

    rerender(<TrackRow track={{ ...track }} index={0} onPlay={vi.fn()} isCurrent />);

    await waitFor(() => expect(screen.getByRole('menu')).toBeInTheDocument());
    expect(getPlaylists).toHaveBeenCalledTimes(1);
  });

  it('does not fetch until the menu is opened', () => {
    render(<TrackRow track={track} index={0} onPlay={vi.fn()} />);

    expect(getPlaylists).not.toHaveBeenCalled();
  });
});

describe('TrackTableRowItem context menu', () => {
  it('fetches playlists once when opened and lists them', async () => {
    render(
      <table>
        <tbody>
          <TrackTableRowItem
            track={track}
            index={0}
            isCurrentTrack={false}
            isPlaying={false}
            onTrackClick={vi.fn()}
            formatDuration={formatDuration}
          />
        </tbody>
      </table>
    );

    await openMenu();

    expect(await screen.findByText(/Road Trip/)).toBeInTheDocument();
    expect(getPlaylists).toHaveBeenCalledTimes(1);
  });
});
