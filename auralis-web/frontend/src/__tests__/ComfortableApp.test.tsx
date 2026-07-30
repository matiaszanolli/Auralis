/**
 * ComfortableApp global keyboard shortcuts vs. the live playback session (#4541)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Before this fix, the Space/Arrow/mute shortcuts went through
 * usePlaybackControl, a legacy REST/WS control plane that never touched the
 * enhanced-audio session Player.tsx actually streams — pressing Space sent a
 * WS `play_normal` command that cancelled the user's own in-flight
 * `stream_enhanced_audio` task server-side with no visible error.
 *
 * These tests render the real ComfortableApp (shortcuts + Player both
 * mounted) wrapped in a single PlaybackSessionProvider, exactly as App.tsx
 * wires it, and assert the shortcuts drive the SAME mocked usePlayEnhanced
 * instance instead of any REST/`play_normal` path.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act } from '@testing-library/react';
import { render } from '@/test/test-utils';
import { PlaybackSessionProvider } from '@/contexts/PlaybackSessionContext';
import ComfortableApp from '../ComfortableApp';

const {
  mockPlayEnhanced,
  mockPausePlayback,
  mockResumePlayback,
  mockStopPlayback,
  mockSetVolume,
  streaming,
} = vi.hoisted(() => ({
  mockPlayEnhanced: vi.fn(),
  mockPausePlayback: vi.fn(),
  mockResumePlayback: vi.fn(),
  mockStopPlayback: vi.fn(),
  mockSetVolume: vi.fn(),
  // Mutable so individual tests can flip isStreaming/isPaused before render.
  streaming: { isStreaming: false, isPaused: false },
}));

vi.mock('@/hooks/enhancement/usePlayEnhanced', () => ({
  usePlayEnhanced: () => ({
    playEnhanced: mockPlayEnhanced,
    seekTo: vi.fn(),
    pausePlayback: mockPausePlayback,
    resumePlayback: mockResumePlayback,
    stopPlayback: mockStopPlayback,
    setVolume: mockSetVolume,
    isStreaming: streaming.isStreaming,
    streamingState: streaming.isStreaming ? 'streaming' : 'idle',
    processedChunks: 0,
    totalChunks: 0,
    currentTime: 0,
    isPaused: streaming.isPaused,
    isSeeking: false,
    error: null,
  }),
}));

vi.mock('@/hooks/enhancement/useEnhancementControl', () => ({
  useEnhancementControl: () => ({ preset: 'adaptive', intensity: 1.0 }),
}));

const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 200,
};

function renderApp(preloadedState?: Parameters<typeof render>[1]) {
  return render(
    <PlaybackSessionProvider>
      <ComfortableApp />
    </PlaybackSessionProvider>,
    preloadedState
  );
}

function pressKey(key: string) {
  act(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
  });
}

describe('ComfortableApp global shortcuts (#4541)', () => {
  beforeEach(() => {
    mockPlayEnhanced.mockClear();
    mockPausePlayback.mockClear();
    mockResumePlayback.mockClear();
    mockStopPlayback.mockClear();
    mockSetVolume.mockClear();
    streaming.isStreaming = false;
    streaming.isPaused = false;
  });

  it('Space starts the enhanced session (not a REST/WS play_normal path) when idle', () => {
    renderApp({
      preloadedState: {
        player: { currentTrack: mockTrack } as never,
      },
    });

    pressKey(' ');

    expect(mockPlayEnhanced).toHaveBeenCalledWith(mockTrack.id, 'adaptive', 1.0);
    expect(mockPausePlayback).not.toHaveBeenCalled();
    expect(mockResumePlayback).not.toHaveBeenCalled();
  });

  it('Space pauses the SAME session (not cancel-and-restart) while streaming', () => {
    streaming.isStreaming = true;
    streaming.isPaused = false;
    renderApp({
      preloadedState: {
        player: { currentTrack: mockTrack } as never,
      },
    });

    pressKey(' ');

    expect(mockPausePlayback).toHaveBeenCalledTimes(1);
    // Must not cancel and re-issue a new stream (the #4541 bug).
    expect(mockPlayEnhanced).not.toHaveBeenCalled();
    expect(mockStopPlayback).not.toHaveBeenCalled();
  });

  it('Space resumes the SAME session while paused', () => {
    streaming.isStreaming = true;
    streaming.isPaused = true;
    renderApp({
      preloadedState: {
        player: { currentTrack: mockTrack } as never,
      },
    });

    pressKey(' ');

    expect(mockResumePlayback).toHaveBeenCalledTimes(1);
    expect(mockPlayEnhanced).not.toHaveBeenCalled();
  });

  it('ArrowRight advances the audio via the live session, not just the queue index', () => {
    renderApp({
      preloadedState: {
        player: { currentTrack: mockTrack } as never,
        queue: {
          tracks: [mockTrack, { ...mockTrack, id: 2, title: 'Next' }],
          currentIndex: 0,
        } as never,
      },
    });

    pressKey('ArrowRight');

    expect(mockStopPlayback).toHaveBeenCalled();
    expect(mockPlayEnhanced).toHaveBeenCalledWith(2, 'adaptive', 1.0);
  });

  it('ArrowLeft plays the previous track via the live session', () => {
    renderApp({
      preloadedState: {
        player: { currentTrack: { ...mockTrack, id: 2 } } as never,
        queue: {
          tracks: [mockTrack, { ...mockTrack, id: 2, title: 'Next' }],
          currentIndex: 1,
        } as never,
      },
    });

    pressKey('ArrowLeft');

    expect(mockStopPlayback).toHaveBeenCalled();
    expect(mockPlayEnhanced).toHaveBeenCalledWith(1, 'adaptive', 1.0);
  });

  it('ArrowUp/ArrowDown volume shortcuts call the live session gain control', () => {
    renderApp({
      preloadedState: {
        player: { currentTrack: mockTrack, volume: 50 } as never,
      },
    });

    pressKey('ArrowUp');

    expect(mockSetVolume).toHaveBeenCalledWith(0.6);
  });

  it("'m' mutes via the live session and restores the prior volume on unmute", () => {
    renderApp({
      preloadedState: {
        player: { currentTrack: mockTrack, volume: 70 } as never,
      },
    });

    pressKey('m');
    expect(mockSetVolume).toHaveBeenLastCalledWith(0);

    pressKey('m');
    expect(mockSetVolume).toHaveBeenLastCalledWith(0.7);
  });
});
