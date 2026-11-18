/**
 * The context menu's add-to-playlist toast follows the returned count (#6436)
 *
 * POST /api/playlists/{id}/tracks answers 200 with `added_count: 0` for an all-duplicate request
 * (and, before #6436, for a swallowed database failure). The handler ignored the count and
 * toasted "Added to ..." either way.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@/test/test-utils';
import * as playlistService from '@/services/playlistService';
import { useTrackContextMenu } from '../useTrackContextMenu';
import type { LibraryTrack } from '@/types/domain';

const toast = vi.hoisted(() => ({ success: vi.fn(), info: vi.fn(), warning: vi.fn(), error: vi.fn() }));

vi.mock('@/components/shared/Toast', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/components/shared/Toast')>()),
  useToast: () => toast,
}));

vi.mock('@/services/playlistService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/playlistService')>()),
  addTracksToPlaylist: vi.fn(),
}));

const addTracksToPlaylist = vi.mocked(playlistService.addTracksToPlaylist);
const track = { id: 7, title: 'T', artist: 'A', album: 'B', duration: 1 } as LibraryTrack;

function setup() {
  return renderHook(() => useTrackContextMenu({ track, onPlay: vi.fn() })).result;
}

beforeEach(() => {
  Object.values(toast).forEach((fn) => fn.mockReset());
  addTracksToPlaylist.mockReset();
});

describe('useTrackContextMenu add-to-playlist', () => {
  it('confirms only when the track was actually added', async () => {
    addTracksToPlaylist.mockResolvedValue(1);
    const hook = setup();

    await act(async () => { await hook.current.handleAddToPlaylist(10, 'Road Trip'); });

    expect(addTracksToPlaylist).toHaveBeenCalledWith(10, [7]);
    expect(toast.success).toHaveBeenCalledWith('Added to "Road Trip"');
    expect(toast.warning).not.toHaveBeenCalled();
  });

  it('does not claim success when nothing was added', async () => {
    addTracksToPlaylist.mockResolvedValue(0);
    const hook = setup();

    await act(async () => { await hook.current.handleAddToPlaylist(10, 'Road Trip'); });

    expect(toast.success).not.toHaveBeenCalled();
    expect(toast.warning).toHaveBeenCalledWith('Nothing was added to "Road Trip"');
  });

  it('applies the same rule to a freshly created playlist, and reports a failed request', async () => {
    addTracksToPlaylist.mockResolvedValueOnce(0).mockRejectedValueOnce(new Error('503'));
    const hook = setup();
    const created = { id: 11, name: 'New' } as playlistService.Playlist;

    await act(async () => { await hook.current.handleCreatePlaylist(created); });
    expect(toast.success).not.toHaveBeenCalled();
    expect(toast.warning).toHaveBeenCalledWith('Nothing was added to "New"');

    await act(async () => { await hook.current.handleCreatePlaylist(created); });
    expect(toast.error).toHaveBeenCalledTimes(1);
    expect(toast.success).not.toHaveBeenCalled();
  });
});
