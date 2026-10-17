/**
 * usePlaylistData keeps the loaded list when a refetch fails (#5645)
 *
 * fetchPlaylists used to catch every error and return [], so a transient
 * failure on a WebSocket-triggered refresh (a slow backend during a scan can
 * hit the 30s timeout) replaced a list that had loaded fine with an empty one
 * and the sidebar claimed "No playlists yet". A failure must surface as
 * `error` and leave `playlists` alone.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';

const { wsHandlers } = vi.hoisted(() => ({
  wsHandlers: { current: null as null | { onPlaylistCreated: () => void } },
}));

vi.mock('@/services/playlistService', () => ({ getPlaylists: vi.fn() }));
vi.mock('../usePlaylistWebSocket', () => ({
  usePlaylistWebSocket: (handlers: { onPlaylistCreated: () => void }) => {
    wsHandlers.current = handlers;
  },
}));

import { getPlaylists } from '@/services/playlistService';
import { usePlaylistData } from '../usePlaylistData';

const focus = { id: 1, name: 'Focus', track_count: 12 };
const night = { id: 2, name: 'Late Night', track_count: 4 };
const page = (...playlists: unknown[]) => ({ playlists, total: playlists.length }) as never;

beforeEach(() => {
  vi.mocked(getPlaylists).mockReset();
  vi.spyOn(console, 'error').mockImplementation(() => undefined);
});

describe('usePlaylistData (#5645)', () => {
  it('loads the list on mount without an error', async () => {
    vi.mocked(getPlaylists).mockResolvedValue(page(focus, night));

    const { result } = renderHook(() => usePlaylistData());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.playlists).toEqual([focus, night]);
    expect(result.current.error).toBeNull();
  });

  it('keeps the existing list and exposes an error when a refresh fails', async () => {
    vi.mocked(getPlaylists).mockResolvedValueOnce(page(focus, night));
    const { result } = renderHook(() => usePlaylistData());
    await waitFor(() => expect(result.current.playlists).toHaveLength(2));

    vi.mocked(getPlaylists).mockRejectedValueOnce(new Error('timeout'));
    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.playlists).toEqual([focus, night]);
    expect(result.current.error).toBe('Failed to load playlists');
  });

  it('keeps the list when a WebSocket-triggered refresh fails (refresh never rejects)', async () => {
    vi.mocked(getPlaylists).mockResolvedValueOnce(page(focus));
    const { result } = renderHook(() => usePlaylistData());
    await waitFor(() => expect(result.current.playlists).toHaveLength(1));

    vi.mocked(getPlaylists).mockRejectedValueOnce(new Error('503'));
    await act(async () => {
      wsHandlers.current!.onPlaylistCreated();
    });

    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.playlists).toEqual([focus]);
  });

  it('reports a failed initial load as an error with an empty list, and stops loading', async () => {
    vi.mocked(getPlaylists).mockRejectedValue(new Error('network'));

    const { result } = renderHook(() => usePlaylistData());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.playlists).toEqual([]);
    expect(result.current.error).toBe('Failed to load playlists');
  });

  it('clears the error once a retry succeeds', async () => {
    vi.mocked(getPlaylists).mockRejectedValueOnce(new Error('network'));
    const { result } = renderHook(() => usePlaylistData());
    await waitFor(() => expect(result.current.error).not.toBeNull());

    vi.mocked(getPlaylists).mockResolvedValueOnce(page(focus));
    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.error).toBeNull();
    expect(result.current.playlists).toEqual([focus]);
  });
});
