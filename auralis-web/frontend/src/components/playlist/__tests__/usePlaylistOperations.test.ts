/**
 * Direct spec for usePlaylistOperations (#5683).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePlaylistOperations } from '../usePlaylistOperations';

const mockSuccess = vi.fn();
const mockError = vi.fn();
const mockDeletePlaylist = vi.fn();

vi.mock('@/components/shared/Toast', () => ({
  useToast: () => ({ success: mockSuccess, error: mockError }),
}));
vi.mock('@/services/playlistService', () => ({
  deletePlaylist: (...args: unknown[]) => mockDeletePlaylist(...args),
}));

describe('usePlaylistOperations.handleDelete', () => {
  let confirmSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    mockDeletePlaylist.mockResolvedValue(undefined);
  });
  afterEach(() => confirmSpy.mockRestore());

  const run = async (props: Parameters<typeof usePlaylistOperations>[0], id = 3) => {
    const { result } = renderHook(() => usePlaylistOperations(props));
    let outcome: boolean | undefined;
    await act(async () => { outcome = await result.current.handleDelete(id, 'Road'); });
    return outcome;
  };

  it('does nothing when the user declines the confirmation', async () => {
    confirmSpy.mockReturnValue(false);
    expect(await run({})).toBe(false);
    expect(confirmSpy).toHaveBeenCalledWith('Delete playlist "Road"?');
    expect(mockDeletePlaylist).not.toHaveBeenCalled();
    expect(mockSuccess).not.toHaveBeenCalled();
  });

  it('deletes, announces success and reports true', async () => {
    expect(await run({})).toBe(true);
    expect(mockDeletePlaylist).toHaveBeenCalledWith(3);
    expect(mockSuccess).toHaveBeenCalledWith('Playlist "Road" deleted');
  });

  it('clears the selection with -1 only when the deleted playlist was the selected one', async () => {
    const onPlaylistSelect = vi.fn();
    await run({ selectedPlaylistId: 3, onPlaylistSelect }, 3);
    expect(onPlaylistSelect).toHaveBeenCalledExactlyOnceWith(-1);

    onPlaylistSelect.mockClear();
    await run({ selectedPlaylistId: 5, onPlaylistSelect }, 3);
    expect(onPlaylistSelect).not.toHaveBeenCalled();
  });

  it('toasts the failure, reports false and leaves the selection alone when the delete rejects', async () => {
    mockDeletePlaylist.mockRejectedValue(new Error('boom'));
    const onPlaylistSelect = vi.fn();

    expect(await run({ selectedPlaylistId: 3, onPlaylistSelect }, 3)).toBe(false);
    expect(mockError).toHaveBeenCalledOnce();
    expect(mockError.mock.calls[0][0]).toContain('Failed to delete playlist');
    expect(mockSuccess).not.toHaveBeenCalled();
    expect(onPlaylistSelect).not.toHaveBeenCalled();
  });
});
