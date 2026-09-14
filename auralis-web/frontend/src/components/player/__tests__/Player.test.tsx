/**
 * Player.tsx orchestration component tests (#2363, #3613)
 *
 * Previously this file mocked the entire `react-redux` module with a
 * hand-rolled selector lookup, which made every test vacuous — no
 * state-driven branch was ever exercised. Since #3613 the suite uses
 * the real Redux Provider via `@/test/test-utils` and seeds slice
 * state through `preloadedState`, so the assertions actually verify
 * what the user sees.
 */

import { beforeEach, describe, it, expect, vi } from 'vitest';
import { screen, fireEvent, waitFor, act } from '@testing-library/react';
import { render } from '@/test/test-utils';
import { initialStreamingInfo } from '@/store/slices/playerStreamingReducers';
import Player from '../Player';

// Captured across renders so tests can assert on the exact wire-mode choice.
const { mockPlayEnhanced, mockPlayNormal, enhancementSettings, session } = vi.hoisted(() => ({
  mockPlayEnhanced: vi.fn(),
  mockPlayNormal: vi.fn(),
  enhancementSettings: { enabled: true },
  // Mutable so a test can put the mocked session mid-stream.
  session: { isStreaming: false, streamingState: 'idle' },
}));

// Heavy hooks remain stubbed — they pull in WebSocket / AudioContext
// machinery that has no analog in jsdom. The Redux integration tests
// can still verify state-driven render branches because Player reads
// playback state from Redux, not from these hooks.
//
// #4541: usePlayEnhanced is now called by PlaybackSessionProvider, not by
// Player.tsx directly — Player wraps its render in the provider below so
// this mock still takes effect the same way it did before the refactor.
vi.mock('@/hooks/enhancement/usePlayEnhanced', () => ({
  usePlayEnhanced: () => ({
    playEnhanced: mockPlayEnhanced,
    playNormal: mockPlayNormal,
    seekTo: vi.fn(),
    pausePlayback: vi.fn(),
    resumePlayback: vi.fn(),
    stopPlayback: vi.fn(),
    isStreaming: session.isStreaming,
    streamingState: session.streamingState,
    processedChunks: 0,
    totalChunks: 0,
    currentTime: 0,
    isPaused: false,
    isSeeking: false,
    setVolume: vi.fn(),
    error: null,
  }),
}));

// Current enhancement selection — Player must pass this to playEnhanced on
// track transitions instead of hardcoded adaptive/1.0 (#4410).
// 'warm' is a deliberately non-'adaptive' sentinel even though it is no
// longer a real preset (#4861 follow-up): this mock is what makes the
// assertion below actually prove pass-through of whatever the hook reports,
// rather than passing vacuously because the mock and the hardcoded default
// happen to look the same.
vi.mock('@/hooks/enhancement/useEnhancementControl', () => ({
  useEnhancementControl: () => ({
    enabled: enhancementSettings.enabled,
    preset: 'warm',
    intensity: 0.5,
  }),
}));

function renderPlayer(...args: Parameters<typeof render>) {
  const [ui, options] = args;
  // #5006: test-utils' AllProviders now wraps every render in
  // PlaybackSessionProvider — wrapping again here would nest two provider
  // instances (a second live usePlayEnhanced() call), which #4541's single-
  // session invariant explicitly forbids even if it happened not to break
  // any assertion here.
  return render(ui, options);
}

const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 200,
};

describe('Player', () => {
  beforeEach(() => {
    enhancementSettings.enabled = true;
    mockPlayEnhanced.mockReset();
    mockPlayNormal.mockReset();
    session.isStreaming = false;
    session.streamingState = 'idle';
  });

  describe('local playback stall (#5461)', () => {
    function renderStreaming(stalled: boolean, streamingState = 'streaming') {
      session.isStreaming = streamingState === 'streaming';
      session.streamingState = streamingState;
      const enhanced = { ...initialStreamingInfo, state: streamingState, stalled };
      return renderPlayer(<Player />, {
        preloadedState: {
          player: {
            currentTrack: mockTrack,
            streaming: { normal: { ...initialStreamingInfo }, enhanced },
          } as never,
        },
      });
    }

    it('shows the buffering indicator while playback is stalled', () => {
      renderStreaming(true);
      expect(screen.getByTestId('buffering-status')).toHaveTextContent('Buffering...');
    });

    it('shows no buffering status while audio is flowing', () => {
      renderStreaming(false);
      expect(screen.queryByTestId('buffering-status')).not.toBeInTheDocument();
    });

    it('does not report the drain after a completed stream as a stall', () => {
      renderStreaming(true, 'complete');
      expect(screen.queryByTestId('buffering-status')).not.toBeInTheDocument();
    });
  });

  it('should render the play button when no track is loaded', () => {
    renderPlayer(<Player />);
    expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
  });

  it('should render the current track title when one is loaded', () => {
    renderPlayer(<Player />, {
      preloadedState: {
        player: { currentTrack: mockTrack } as never,
      },
    });
    expect(screen.getByText('Test Track')).toBeInTheDocument();
  });

  it('should render the previous and next track buttons', () => {
    renderPlayer(<Player />, {
      preloadedState: {
        player: { currentTrack: mockTrack } as never,
        queue: {
          tracks: [mockTrack, { ...mockTrack, id: 2, title: 'Next' }],
          currentIndex: 0,
        } as never,
      },
    });
    // Both transport buttons present when a queue has multiple entries.
    expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
  });

  it('Next passes the current preset/intensity, not hardcoded adaptive/1.0 (#4410)', async () => {
    renderPlayer(<Player />, {
      preloadedState: {
        player: { currentTrack: mockTrack } as never,
        queue: {
          tracks: [mockTrack, { ...mockTrack, id: 2, title: 'Next' }],
          currentIndex: 0,
        } as never,
      },
    });

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => expect(mockPlayEnhanced).toHaveBeenCalled());
    expect(mockPlayEnhanced).toHaveBeenCalledWith(2, 'warm', 0.5);
  });

  it('Next uses normal playback when enhancement is disabled (#4812)', async () => {
    enhancementSettings.enabled = false;
    renderPlayer(<Player />, {
      preloadedState: {
        player: { currentTrack: mockTrack } as never,
        queue: {
          tracks: [mockTrack, { ...mockTrack, id: 2, title: 'Next' }],
          currentIndex: 0,
        } as never,
      },
    });

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => expect(mockPlayNormal).toHaveBeenCalledWith(2));
    expect(mockPlayEnhanced).not.toHaveBeenCalled();
  });

  it('coalesces rapid Next clicks while the playback request is pending (#4835)', async () => {
    let resolvePlayback!: () => void;
    mockPlayEnhanced.mockImplementationOnce(() => new Promise<void>((resolve) => {
      resolvePlayback = resolve;
    }));

    renderPlayer(<Player />, {
      preloadedState: {
        player: { currentTrack: mockTrack } as never,
        queue: {
          tracks: [
            mockTrack,
            { ...mockTrack, id: 2, title: 'Next' },
            { ...mockTrack, id: 3, title: 'Later' },
          ],
          currentIndex: 0,
        } as never,
      },
    });

    const nextButton = screen.getByRole('button', { name: /next/i });
    fireEvent.click(nextButton);
    fireEvent.click(nextButton);

    expect(mockPlayEnhanced).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(nextButton).toBeDisabled());

    await act(async () => {
      resolvePlayback();
    });
    await waitFor(() => expect(nextButton).not.toBeDisabled());
  });

  it('should render the queue panel toggle', () => {
    renderPlayer(<Player />);
    // QueuePanel toggle is rendered as part of the right-side action group.
    // Looser query because the exact aria label can drift; the absence of
    // the queue toggle would be a structural regression worth catching.
    const queueButton =
      screen.queryByRole('button', { name: /queue/i }) ||
      screen.queryByTestId?.('queue-toggle');
    expect(queueButton).toBeTruthy();
  });
});
