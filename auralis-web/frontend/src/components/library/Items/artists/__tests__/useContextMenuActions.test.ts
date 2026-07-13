/**
 * useContextMenuActions — artist context-menu action ordering (#4444)
 *
 * "Add artist to queue" previously showed the success toast as the FIRST
 * statement of its try block, before the fetch that can fail/return empty — so
 * a failure produced a false "Added…" toast immediately followed by an error.
 * Success must fire only after the tracks are actually queued.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// vi.hoisted so these spies exist before the (hoisted) vi.mock factories run.
const { success, showError, addMany, clearQueue, setQueue, play } = vi.hoisted(() => ({
  success: vi.fn(),
  showError: vi.fn(),
  addMany: vi.fn(),
  clearQueue: vi.fn(),
  setQueue: vi.fn(),
  play: vi.fn(),
}));

vi.mock('@/components/shared/Toast', () => ({
  useToast: () => ({ success, error: showError }),
}));
vi.mock('@/hooks/shared/useReduxState', () => ({
  useQueue: () => ({ clear: clearQueue, setQueue, addMany }),
  usePlayerActions: () => ({ play }),
}));
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
  return result.current.actions as unknown as { onAddToQueue: () => Promise<void> };
}

describe('useContextMenuActions › handleAddToQueue (#4444)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows NO success toast when the fetch rejects', async () => {
    mockGetArtistTracks.mockRejectedValueOnce(new Error('network down'));
    const actions = renderActions();

    await act(async () => {
      await actions.onAddToQueue();
    });

    expect(success).not.toHaveBeenCalled();
    expect(addMany).not.toHaveBeenCalled();
    expect(showError).toHaveBeenCalledWith('network down');
  });

  it('shows NO success toast when the artist has no tracks', async () => {
    mockGetArtistTracks.mockResolvedValueOnce({ tracks: [] });
    const actions = renderActions();

    await act(async () => {
      await actions.onAddToQueue();
    });

    expect(success).not.toHaveBeenCalled();
    expect(addMany).not.toHaveBeenCalled();
    expect(showError).toHaveBeenCalledWith('No tracks found for Radiohead');
  });

  it('shows success only AFTER the tracks are added', async () => {
    mockGetArtistTracks.mockResolvedValueOnce({
      tracks: [{ id: 1, title: 'Track', album: 'Album', duration: 200 }],
    });
    const actions = renderActions();

    await act(async () => {
      await actions.onAddToQueue();
    });

    expect(addMany).toHaveBeenCalledTimes(1);
    expect(success).toHaveBeenCalledWith('Added Radiohead to queue');
    // Ordering: addMany must have been invoked before the success toast.
    expect(addMany.mock.invocationCallOrder[0]).toBeLessThan(
      success.mock.invocationCallOrder[0]
    );
    expect(showError).not.toHaveBeenCalled();
  });
});
