/**
 * usePlaylistContextActions.onPlay (#4040)
 *
 * "Play" was a stub: it toasted "Playing playlist" and navigated but never
 * fetched tracks or touched the queue. It now fetches the playlist, replaces
 * the queue (Redux dispatch via setQueue), and starts the first track.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePlaylistContextActions } from '../usePlaylistContextActions';
import * as playlistService from '@/services/playlistService';

const mockSetQueue = vi.fn().mockResolvedValue(undefined);
const mockSend = vi.fn();
const mockInfo = vi.fn();
const mockSuccess = vi.fn();
const mockError = vi.fn();

vi.mock('@/services/playlistService', () => ({ getPlaylist: vi.fn() }));
vi.mock('@/hooks/player/usePlaybackQueue', () => ({
  usePlaybackQueue: () => ({ setQueue: mockSetQueue }),
}));
vi.mock('@/contexts/WebSocketContext', () => ({
  useWebSocketContext: () => ({ send: mockSend }),
}));
vi.mock('@/components/shared/Toast', () => ({
  useToast: () => ({ info: mockInfo, success: mockSuccess, error: mockError }),
}));

const playlist = { id: 7, name: 'Roadtrip' } as any;
const tracks = [
  { id: 11, title: 'One' },
  { id: 12, title: 'Two' },
] as any[];

function playAction(onPlaylistSelect = vi.fn()) {
  const { result } = renderHook(() =>
    usePlaylistContextActions({ playlist, onPlaylistSelect, onDelete: vi.fn(), onEdit: vi.fn() })
  );
  const action = result.current.find((a: any) => a.id === 'play');
  return { action, onPlaylistSelect };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('usePlaylistContextActions.onPlay (#4040)', () => {
  it('fetches the playlist, replaces the queue, and starts the first track', async () => {
    vi.mocked(playlistService.getPlaylist).mockResolvedValue({ ...playlist, tracks } as any);

    const { action, onPlaylistSelect } = playAction();
    await act(async () => {
      await Promise.resolve(action!.onClick());
    });

    expect(playlistService.getPlaylist).toHaveBeenCalledWith(7);
    // Redux queue dispatch with the fetched tracks.
    expect(mockSetQueue).toHaveBeenCalledWith(tracks, 0);
    // Playback started for the first track.
    expect(mockSend).toHaveBeenCalledWith({
      type: 'play_enhanced',
      data: { track_id: 11, preset: 'adaptive', intensity: 1.0 },
    });
    expect(mockSuccess).toHaveBeenCalledWith(expect.stringContaining('Roadtrip'));
    expect(onPlaylistSelect).toHaveBeenCalledWith(7);
  });

  it('shows a "no tracks" notice and does not queue for an empty playlist', async () => {
    vi.mocked(playlistService.getPlaylist).mockResolvedValue({ ...playlist, tracks: [] } as any);

    const { action } = playAction();
    await act(async () => {
      await Promise.resolve(action!.onClick());
    });

    expect(mockInfo).toHaveBeenCalledWith(expect.stringContaining('no tracks'));
    expect(mockSetQueue).not.toHaveBeenCalled();
    expect(mockSend).not.toHaveBeenCalled();
    expect(mockSuccess).not.toHaveBeenCalled();
  });

  it('shows an error toast when fetching the playlist fails', async () => {
    vi.mocked(playlistService.getPlaylist).mockRejectedValue(new Error('boom'));

    const { action } = playAction();
    await act(async () => {
      await Promise.resolve(action!.onClick());
    });

    expect(mockError).toHaveBeenCalledWith(expect.stringContaining('Roadtrip'));
    expect(mockSetQueue).not.toHaveBeenCalled();
  });
});
