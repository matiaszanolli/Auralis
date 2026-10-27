/**
 * useContextMenuActions — artist context-menu queue actions
 *
 * #4444: "Add artist to queue" previously showed the success toast as the FIRST
 * statement of its try block, before the fetch that can fail/return empty — so
 * a failure produced a false "Added…" toast immediately followed by an error.
 * Success must fire only after the tracks are actually queued.
 *
 * #5612: the queue actions used to dispatch to the Redux queue only — the engine
 * queue never changed, "Play All" started no stream (setIsPlaying alone starts
 * nothing) and a success toast was shown anyway. They now call the backend and
 * start the first track through the playback session.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// vi.hoisted so these spies exist before the (hoisted) vi.mock factories run.
const { success, showError, addTracksToQueue, setQueue, startTrack } = vi.hoisted(() => ({
  success: vi.fn(),
  showError: vi.fn(),
  addTracksToQueue: vi.fn(),
  setQueue: vi.fn(),
  startTrack: vi.fn(),
}));

vi.mock('@/components/shared/Toast', () => ({
  useToast: () => ({ success, error: showError }),
}));
vi.mock('@/contexts/PlaybackSessionContext', () => ({
  usePlaybackControls: () => ({ startTrack }),
}));
vi.mock('@/services/queueService', () => ({ addTracksToQueue, setQueue }));
vi.mock('@/services/libraryService', () => ({
  getArtistTracks: vi.fn(),
}));
// Passthrough so we can invoke the registered handlers directly.
vi.mock('@/components/shared/ContextMenu', () => ({
  getArtistContextActions: (handlers: Record<string, () => void>) => handlers,
}));

import { getArtistTracks } from '@/services/libraryService';
import { useContextMenuActions } from '../useContextMenuActions';

const mockGetArtistTracks = getArtistTracks as ReturnType<typeof vi.fn>;
const artist = { id: 7, name: 'Radiohead' } as any;

function renderActions() {
  const { result } = renderHook(() => useContextMenuActions({ artist }));
  return result.current.actions as unknown as {
    onAddToQueue: () => Promise<void>;
    onPlayAll: () => Promise<void>;
  };
}

const apiTrack = (id: number) => ({ id, title: `Track ${id}`, album: 'Album', duration: 200 });

beforeEach(() => {
  vi.clearAllMocks();
  addTracksToQueue.mockResolvedValue({ added_count: 3, requested_count: 3, queue_size: 3 });
  setQueue.mockResolvedValue(undefined);
  startTrack.mockResolvedValue(undefined);
});

describe('useContextMenuActions › handleAddToQueue (#4444, #5612)', () => {
  it('shows NO success toast when the fetch rejects', async () => {
    mockGetArtistTracks.mockRejectedValueOnce(new Error('network down'));
    const actions = renderActions();

    await act(async () => {
      await actions.onAddToQueue();
    });

    expect(success).not.toHaveBeenCalled();
    expect(addTracksToQueue).not.toHaveBeenCalled();
    expect(showError).toHaveBeenCalledWith('network down');
  });

  it('shows NO success toast when the artist has no tracks', async () => {
    mockGetArtistTracks.mockResolvedValueOnce({ tracks: [] });
    const actions = renderActions();

    await act(async () => {
      await actions.onAddToQueue();
    });

    expect(success).not.toHaveBeenCalled();
    expect(addTracksToQueue).not.toHaveBeenCalled();
    expect(showError).toHaveBeenCalledWith('No tracks found for Radiohead');
  });

  it('adds every track in ONE batch call, in album order, then shows success', async () => {
    mockGetArtistTracks.mockResolvedValueOnce({ tracks: [apiTrack(1), apiTrack(2), apiTrack(3)] });
    const actions = renderActions();

    await act(async () => {
      await actions.onAddToQueue();
    });

    expect(addTracksToQueue).toHaveBeenCalledTimes(1);
    expect(addTracksToQueue).toHaveBeenCalledWith([1, 2, 3]);
    expect(success).toHaveBeenCalledWith('Added Radiohead to queue');
    expect(addTracksToQueue.mock.invocationCallOrder[0]).toBeLessThan(
      success.mock.invocationCallOrder[0]
    );
    expect(showError).not.toHaveBeenCalled();
  });

  it('reports a partial add, and no success, when the backend skips tracks', async () => {
    mockGetArtistTracks.mockResolvedValueOnce({ tracks: [apiTrack(1), apiTrack(2), apiTrack(3)] });
    addTracksToQueue.mockResolvedValueOnce({ added_count: 2, requested_count: 3, queue_size: 2 });
    const actions = renderActions();

    await act(async () => {
      await actions.onAddToQueue();
    });

    expect(success).not.toHaveBeenCalled();
    expect(showError).toHaveBeenCalledWith('Added 2 of 3 tracks to queue');
  });

  it('shows the backend error, and no success, when the batch call fails', async () => {
    mockGetArtistTracks.mockResolvedValueOnce({ tracks: [apiTrack(1)] });
    addTracksToQueue.mockRejectedValueOnce(new Error('queue full'));
    const actions = renderActions();

    await act(async () => {
      await actions.onAddToQueue();
    });

    expect(success).not.toHaveBeenCalled();
    expect(showError).toHaveBeenCalledWith('queue full');
  });
});
