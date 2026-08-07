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
import ComfortableApp from '../ComfortableApp';

const {
  mockPlayEnhanced,
  mockPausePlayback,
  mockResumePlayback,
  mockStopPlayback,
  mockSetVolume,
  mockInfo,
  streaming,
} = vi.hoisted(() => ({
  mockPlayEnhanced: vi.fn(),
  mockPausePlayback: vi.fn(),
  mockResumePlayback: vi.fn(),
  mockStopPlayback: vi.fn(),
  mockSetVolume: vi.fn(),
  mockInfo: vi.fn(),
  // Mutable so individual tests can flip isStreaming/isPaused before render.
  streaming: { isStreaming: false, isPaused: false },
}));

// #5008: spy on the toast `info()` call so the "false confirmation on a
// dropped command" regression test can assert it. ToastProvider must still
// be exported as a passthrough — AllProviders (test-utils) renders it.
vi.mock('@/components/shared/Toast', () => ({
  useToast: () => ({ info: mockInfo, success: vi.fn(), error: vi.fn() }),
  ToastProvider: ({ children }: any) => children,
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
  // #5005: `enabled` was missing here, so `startTrackForSettings` always
  // fell through to the (also unmocked) `playNormal` branch — this test
  // suite never actually exercised the enhanced path it exists to verify,
  // masked until now by the render crash fixed in test-utils.tsx.
  useEnhancementControl: () => ({ enabled: true, preset: 'adaptive', intensity: 1.0 }),
}));

const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 200,
};

function renderApp(preloadedState?: Parameters<typeof render>[1]) {
  // #5005: test-utils' AllProviders now wraps every render in
  // PlaybackSessionProvider (matching App.tsx's single-provider structure) —
  // wrapping again here would nest two provider instances and defeat the
  // "one shared session" invariant this suite exists to verify.
  return render(<ComfortableApp />, preloadedState);
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
    mockInfo.mockClear();
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

  it('#5008: a command dropped while another is in flight does not fire a false confirmation toast', async () => {
    // Hold the first command pending so runTransportCommand's shared
    // commandPendingRef guard is still held when the second command fires.
    let resolvePlayEnhanced: () => void = () => {};
    mockPlayEnhanced.mockImplementationOnce(
      () => new Promise<void>((resolve) => { resolvePlayEnhanced = resolve; })
    );

    renderApp({
      preloadedState: {
        player: { currentTrack: mockTrack } as never,
      },
    });

    pressKey(' '); // starts the enhanced session; commandPendingRef is now held
    expect(mockInfo).toHaveBeenCalledWith('Playing'); // the command that IS running still confirms

    // A different command fires while the first is still in flight — must be
    // dropped silently, not falsely confirmed.
    pressKey('ArrowRight');

    expect(mockInfo).not.toHaveBeenCalledWith('Next track');
    // The dropped command's own side effect must not have run either —
    // confirms the guard suppressed the toast because the command was
    // genuinely dropped, not because of an unrelated toast bug.
    expect(mockStopPlayback).not.toHaveBeenCalled();

    // Let the first command settle so the pending flag clears cleanly and
    // doesn't leak into other tests.
    await act(async () => {
      resolvePlayEnhanced();
      await Promise.resolve();
    });
  });
});
