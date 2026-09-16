/**
 * PlaybackSessionContext transport logic tests (#5399)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `handleNext` has direct coverage via Player.test.tsx (#4410, #4812, #4835),
 * but `handlePrevious`, `handleMuteToggle` (including its 0-1/0-100 volume
 * round trip), and the auto-advance effect (guarded by `hasAutoAdvancedRef`)
 * were never exercised directly — only through prop-callback assertions in
 * PlaybackControls.test.tsx/VolumeControl.test.tsx, or re-render isolation
 * in PlaybackSessionContext.split.test.tsx (#5006). This file mirrors the
 * handleNext pattern for those three paths.
 */

import { beforeEach, describe, it, expect, vi } from 'vitest';
import { act } from 'react';
import { render } from '@/test/test-utils';
import { usePlaybackControls } from '@/contexts/PlaybackSessionContext';
import type { PlaybackControlsContextValue } from '@/contexts/playbackSessionContexts';
import { selectVolume, selectIsMuted } from '@/store/slices/playerSlice';

const { mockPlayEnhanced, mockPlayNormal, mockStopPlayback, mockSetVolume, enhancementSettings, session } =
  vi.hoisted(() => ({
    mockPlayEnhanced: vi.fn(),
    mockPlayNormal: vi.fn(),
    mockStopPlayback: vi.fn(),
    mockSetVolume: vi.fn(),
    enhancementSettings: { enabled: true },
    // Mutable so a test can drive streamingState/currentTime across a rerender.
    session: { isStreaming: false, streamingState: 'idle' as string, currentTime: 0 },
  }));

vi.mock('@/hooks/enhancement/usePlayEnhanced', () => ({
  usePlayEnhanced: () => ({
    playEnhanced: mockPlayEnhanced,
    playNormal: mockPlayNormal,
    seekTo: vi.fn(),
    pausePlayback: vi.fn(),
    resumePlayback: vi.fn(),
    stopPlayback: mockStopPlayback,
    isStreaming: session.isStreaming,
    streamingState: session.streamingState,
    processedChunks: 0,
    totalChunks: 0,
    currentTime: session.currentTime,
    isPaused: false,
    isSeeking: false,
    setVolume: mockSetVolume,
    error: null,
  }),
}));

vi.mock('@/hooks/enhancement/useEnhancementControl', () => ({
  useEnhancementControl: () => ({
    enabled: enhancementSettings.enabled,
    preset: 'warm',
    intensity: 0.5,
  }),
}));

const mockTrack = { id: 1, title: 'Track A', artist: 'Artist', album: 'Album', duration: 200 };
const mockTrack2 = { id: 2, title: 'Track B', artist: 'Artist', album: 'Album', duration: 200 };
const mockTrack3 = { id: 3, title: 'Track C', artist: 'Artist', album: 'Album', duration: 200 };

/** Captures the live usePlaybackControls() value onto `out` on every render,
 * so the test can call handlers directly without reimplementing a UI. */
function ControlsCapture({ out }: { out: { value?: PlaybackControlsContextValue } }) {
  out.value = usePlaybackControls();
  return null;
}

describe('PlaybackSessionContext transport logic (#5399)', () => {
  beforeEach(() => {
    enhancementSettings.enabled = true;
    mockPlayEnhanced.mockReset();
    mockPlayNormal.mockReset();
    mockStopPlayback.mockReset();
    mockSetVolume.mockReset();
    session.isStreaming = false;
    session.streamingState = 'idle';
    session.currentTime = 0;
  });

  describe('handlePrevious', () => {
    it('does nothing when already at the first track in the queue', async () => {
      const out: { value?: PlaybackControlsContextValue } = {};
      render(<ControlsCapture out={out} />, {
        preloadedState: {
          player: { currentTrack: mockTrack } as never,
          queue: { tracks: [mockTrack, mockTrack2], currentIndex: 0 } as never,
        },
      });

      await act(async () => {
        await out.value!.handlePrevious();
      });

      expect(mockStopPlayback).not.toHaveBeenCalled();
      expect(mockPlayEnhanced).not.toHaveBeenCalled();
      expect(mockPlayNormal).not.toHaveBeenCalled();
    });

    it('stops playback and starts the previous track with the current preset/intensity', async () => {
      const out: { value?: PlaybackControlsContextValue } = {};
      render(<ControlsCapture out={out} />, {
        preloadedState: {
          player: { currentTrack: mockTrack2 } as never,
          queue: { tracks: [mockTrack, mockTrack2], currentIndex: 1 } as never,
        },
      });

      await act(async () => {
        await out.value!.handlePrevious();
      });

      expect(mockStopPlayback).toHaveBeenCalledTimes(1);
      expect(mockPlayEnhanced).toHaveBeenCalledWith(mockTrack.id, 'warm', 0.5);
    });

    it('uses normal playback when enhancement is disabled', async () => {
      enhancementSettings.enabled = false;
      const out: { value?: PlaybackControlsContextValue } = {};
      render(<ControlsCapture out={out} />, {
        preloadedState: {
          player: { currentTrack: mockTrack2 } as never,
          queue: { tracks: [mockTrack, mockTrack2], currentIndex: 1 } as never,
        },
      });

      await act(async () => {
        await out.value!.handlePrevious();
      });

      expect(mockPlayNormal).toHaveBeenCalledWith(mockTrack.id);
      expect(mockPlayEnhanced).not.toHaveBeenCalled();
    });

    it('coalesces rapid Previous calls while the playback request is pending (mirrors #4835)', async () => {
      let resolvePlayback!: () => void;
      mockPlayEnhanced.mockImplementationOnce(
        () => new Promise<void>((resolve) => { resolvePlayback = resolve; })
      );

      const out: { value?: PlaybackControlsContextValue } = {};
      render(<ControlsCapture out={out} />, {
        preloadedState: {
          player: { currentTrack: mockTrack3 } as never,
          queue: { tracks: [mockTrack, mockTrack2, mockTrack3], currentIndex: 2 } as never,
        },
      });

      let firstCall!: Promise<void>;
      let secondCall!: Promise<void>;
      act(() => {
        firstCall = out.value!.handlePrevious();
        secondCall = out.value!.handlePrevious();
      });

      expect(mockPlayEnhanced).toHaveBeenCalledTimes(1);

      await act(async () => {
        resolvePlayback();
        await Promise.all([firstCall, secondCall]);
      });

      // The second, coalesced call must not have issued its own command.
      expect(mockPlayEnhanced).toHaveBeenCalledTimes(1);
    });
  });

  describe('handleMuteToggle', () => {
    it('mutes by zeroing volume and restores the exact pre-mute volume on unmute (0-1/0-100 round trip)', async () => {
      const out: { value?: PlaybackControlsContextValue } = {};
      const { store } = render(<ControlsCapture out={out} />, {
        preloadedState: {
          player: { currentTrack: mockTrack, volume: 80, isMuted: false } as never,
        },
      });

      let mutedResult: boolean | undefined;
      await act(async () => {
        mutedResult = await out.value!.handleMuteToggle();
      });

      expect(mutedResult).toBe(true);
      expect(selectVolume(store.getState())).toBe(0);
      // handleVolumeChange forwards the 0-1 range to the streaming engine.
      expect(mockSetVolume).toHaveBeenLastCalledWith(0);

      let unmutedResult: boolean | undefined;
      await act(async () => {
        unmutedResult = await out.value!.handleMuteToggle();
      });

      expect(unmutedResult).toBe(false);
      // Exact restore: 80 (0-100) -> 0.8 (0-1) -> 80 (0-100), no drift.
      expect(selectVolume(store.getState())).toBe(80);
      expect(mockSetVolume).toHaveBeenLastCalledWith(0.8);
      expect(selectIsMuted(store.getState())).toBe(false);
    });

    it('treats isMuted=true at volume>0 as muted, but unmuting falls back to the 50% ref default', async () => {
      // The component's own isMuted check is `volume === 0 || playerIsMuted
      // === true` — a track loaded already muted (isMuted flag set) at a
      // nonzero persisted volume (40) is correctly treated as muted here.
      // But preMuteVolumeRef starts at a hardcoded 0.5 and is only ever
      // written by the *mute* branch — a session that mounts already-muted
      // never populates it from the persisted volume, so unmuting restores
      // 50%, not the original 40%. This pins that real, surprising gap
      // rather than asserting the (wrong) assumption that it round-trips.
      const out: { value?: PlaybackControlsContextValue } = {};
      const { store } = render(<ControlsCapture out={out} />, {
        preloadedState: {
          player: { currentTrack: mockTrack, volume: 40, isMuted: true } as never,
        },
      });

      let result: boolean | undefined;
      await act(async () => {
        result = await out.value!.handleMuteToggle();
      });

      expect(result).toBe(false);
      expect(selectVolume(store.getState())).toBe(50);
    });
  });

  describe('auto-advance effect (hasAutoAdvancedRef guard)', () => {
    it('advances to the next track once streaming completes near the end', async () => {
      const out: { value?: PlaybackControlsContextValue } = {};
      session.streamingState = 'streaming';
      session.currentTime = 100; // well before duration - 0.5

      const { rerender } = render(<ControlsCapture out={out} />, {
        preloadedState: {
          player: { currentTrack: mockTrack } as never,
          queue: { tracks: [mockTrack, mockTrack2], currentIndex: 0 } as never,
        },
      });

      expect(mockStopPlayback).not.toHaveBeenCalled();

      session.streamingState = 'complete';
      session.currentTime = 199.6; // >= duration(200) - 0.5
      await act(async () => {
        rerender(<ControlsCapture out={out} />);
      });

      expect(mockStopPlayback).toHaveBeenCalledTimes(1);
      expect(mockPlayEnhanced).toHaveBeenCalledWith(mockTrack2.id, 'warm', 0.5);
    });

    it('does not auto-advance a second time on a subsequent render in the same completed state', async () => {
      // A 3-track queue so `hasMoreTracks` is still true for the *new*
      // current track (index 1 of 3) after the first auto-advance moves the
      // queue forward — otherwise the queue-index change alone would make
      // hasMoreTracks false and mask whether hasAutoAdvancedRef is doing
      // anything at all (confirmed by temporarily deleting the guard: with
      // only 2 tracks this test kept passing for the wrong reason).
      const out: { value?: PlaybackControlsContextValue } = {};
      session.streamingState = 'complete';
      session.currentTime = 199.9;

      const { rerender } = render(<ControlsCapture out={out} />, {
        preloadedState: {
          player: { currentTrack: mockTrack } as never,
          queue: { tracks: [mockTrack, mockTrack2, mockTrack3], currentIndex: 0 } as never,
        },
      });

      expect(mockStopPlayback).toHaveBeenCalledTimes(1);
      expect(mockPlayEnhanced).toHaveBeenLastCalledWith(mockTrack2.id, 'warm', 0.5);

      // A further tick with the same completed/near-end state (e.g. a
      // trailing position update) must not fire a second auto-advance, even
      // though hasMoreTracks is still true for track B (index 1 of 3).
      session.currentTime = 200;
      await act(async () => {
        rerender(<ControlsCapture out={out} />);
      });

      expect(mockStopPlayback).toHaveBeenCalledTimes(1);
      expect(mockPlayEnhanced).toHaveBeenCalledTimes(1);
    });

    it('does not advance when there is no next track in the queue', async () => {
      const out: { value?: PlaybackControlsContextValue } = {};
      session.streamingState = 'complete';
      session.currentTime = 199.9;

      render(<ControlsCapture out={out} />, {
        preloadedState: {
          player: { currentTrack: mockTrack2 } as never,
          queue: { tracks: [mockTrack, mockTrack2], currentIndex: 1 } as never,
        },
      });

      expect(mockStopPlayback).not.toHaveBeenCalled();
      expect(mockPlayEnhanced).not.toHaveBeenCalled();
    });
  });
});
