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
const { success, showError, addTrackToQueue, setQueue, startTrack } = vi.hoisted(() => ({
  success: vi.fn(),
  showError: vi.fn(),
  addTrackToQueue: vi.fn(),
  setQueue: vi.fn(),
  startTrack: vi.fn(),
}));

vi.mock('@/components/shared/Toast', () => ({
  useToast: () => ({ success, error: showError }),
}));
vi.mock('@/contexts/PlaybackSessionContext', () => ({
  usePlaybackControls: () => ({ startTrack }),
}));
vi.mock('@/services/queueService', () => ({ addTrackToQueue, setQueue }));
vi.mock('@/services/libraryService', () => ({
  getArtistTracks: vi.fn(),
}));
// Passthrough so we can invoke the registered handlers directly.
vi.mock('@/components/shared/ContextMenu', () => ({
  getArtistContextActions: (_id: number, handlers: Record<string, () => void>) => handlers,
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
  addTrackToQueue.mockResolvedValue(undefined);
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
    expect(addTrackToQueue).not.toHaveBeenCalled();
    expect(showError).toHaveBeenCalledWith('network down');
  });

  it('shows NO success toast when the artist has no tracks', async () => {
    mockGetArtistTracks.mockResolvedValueOnce({ tracks: [] });
    const actions = renderActions();

    await act(async () => {
      await actions.onAddToQueue();
    });

    expect(success).not.toHaveBeenCalled();
    expect(addTrackToQueue).not.toHaveBeenCalled();
    expect(showError).toHaveBeenCalledWith('No tracks found for Radiohead');
  });

  it('adds every track to the engine queue, in order, then shows success', async () => {
    mockGetArtistTracks.mockResolvedValueOnce({ tracks: [apiTrack(1), apiTrack(2), apiTrack(3)] });
    const actions = renderActions();

    await act(async () => {
      await actions.onAddToQueue();
    });

    expect(addTrackToQueue.mock.calls.map((c) => c[0])).toEqual([1, 2, 3]);
    expect(success).toHaveBeenCalledWith('Added Radiohead to queue');
    // Ordering: the last backend add must precede the success toast.
    expect(addTrackToQueue.mock.invocationCallOrder[2]).toBeLessThan(
      success.mock.invocationCallOrder[0]
    );
    expect(showError).not.toHaveBeenCalled();
  });

  it('waits for each add before sending the next, so queue order is the album order', async () => {
    mockGetArtistTracks.mockResolvedValueOnce({ tracks: [apiTrack(1), apiTrack(2)] });
    let releaseFirst!: () => void;
    addTrackToQueue.mockImplementationOnce(
      () => new Promise<void>((resolve) => { releaseFirst = resolve; })
    );
    const actions = renderActions();

    let done!: Promise<void>;
    await act(async () => {
      done = actions.onAddToQueue();
      await Promise.resolve();
    });
    expect(addTrackToQueue).toHaveBeenCalledTimes(1);

    await act(async () => {
      releaseFirst();
      await done;
    });
    expect(addTrackToQueue.mock.calls.map((c) => c[0])).toEqual([1, 2]);
  });

  it('reports how far it got, and no success, when the backend fails part-way', async () => {
    mockGetArtistTracks.mockResolvedValueOnce({ tracks: [apiTrack(1), apiTrack(2), apiTrack(3)] });
    addTrackToQueue
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error('queue full'));
    const actions = renderActions();

    await act(async () => {
      await actions.onAddToQueue();
    });

    expect(addTrackToQueue).toHaveBeenCalledTimes(2);
    expect(success).not.toHaveBeenCalled();
    expect(showError).toHaveBeenCalledWith('Added 1 of 3 tracks to queue: queue full');
  });

  it('shows the backend error when the very first add fails', async () => {
    mockGetArtistTracks.mockResolvedValueOnce({ tracks: [apiTrack(1)] });
    addTrackToQueue.mockRejectedValueOnce(new Error('Track 1 not found'));
    const actions = renderActions();

    await act(async () => {
      await actions.onAddToQueue();
    });

    expect(success).not.toHaveBeenCalled();
    expect(showError).toHaveBeenCalledWith('Track 1 not found');
  });
});

describe('useContextMenuActions › handlePlayAll (#5612)', () => {
  it('replaces the engine queue, streams the first track, and only then reports success', async () => {
    mockGetArtistTracks.mockResolvedValueOnce({ tracks: [apiTrack(4), apiTrack(5), apiTrack(6)] });
    const actions = renderActions();

    await act(async () => {
      await actions.onPlayAll();
    });

    expect(setQueue).toHaveBeenCalledWith([4, 5, 6], 0);
    expect(startTrack).toHaveBeenCalledWith(4);
    expect(setQueue.mock.invocationCallOrder[0]).toBeLessThan(startTrack.mock.invocationCallOrder[0]);
    expect(startTrack.mock.invocationCallOrder[0]).toBeLessThan(success.mock.invocationCallOrder[0]);
    expect(success).toHaveBeenCalledWith('Playing all songs by Radiohead');
  });

  it('starts nothing and shows the error when the queue cannot be set', async () => {
    mockGetArtistTracks.mockResolvedValueOnce({ tracks: [apiTrack(4)] });
    setQueue.mockRejectedValueOnce(new Error('Track 4 not found'));
    const actions = renderActions();

    await act(async () => {
      await actions.onPlayAll();
    });

    expect(startTrack).not.toHaveBeenCalled();
    expect(success).not.toHaveBeenCalled();
    expect(showError).toHaveBeenCalledWith('Track 4 not found');
  });

  it('does nothing for an artist with no tracks', async () => {
    mockGetArtistTracks.mockResolvedValueOnce({ tracks: [] });
    const actions = renderActions();

    await act(async () => {
      await actions.onPlayAll();
    });

    expect(setQueue).not.toHaveBeenCalled();
    expect(startTrack).not.toHaveBeenCalled();
    expect(showError).toHaveBeenCalledWith('No tracks found for Radiohead');
  });
});
