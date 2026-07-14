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

import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { render } from '@/test/test-utils';
import Player from '../Player';

// Captured across renders so tests can assert on the exact playEnhanced args.
const { mockPlayEnhanced } = vi.hoisted(() => ({ mockPlayEnhanced: vi.fn() }));

// Heavy hooks remain stubbed — they pull in WebSocket / AudioContext
// machinery that has no analog in jsdom. The Redux integration tests
// can still verify state-driven render branches because Player reads
// playback state from Redux, not from these hooks.
vi.mock('@/hooks/enhancement/usePlayEnhanced', () => ({
  usePlayEnhanced: () => ({
    playEnhanced: mockPlayEnhanced,
    seekTo: vi.fn(),
    pausePlayback: vi.fn(),
    resumePlayback: vi.fn(),
    stopPlayback: vi.fn(),
    isStreaming: false,
    streamingProgress: 0,
    setStreamingVolume: vi.fn(),
    error: null,
  }),
}));

// Current enhancement selection — Player must pass this to playEnhanced on
// track transitions instead of hardcoded adaptive/1.0 (#4410).
vi.mock('@/hooks/enhancement/useEnhancementControl', () => ({
  useEnhancementControl: () => ({ preset: 'warm', intensity: 0.5 }),
}));

const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 200,
};

describe('Player', () => {
  it('should render the play button when no track is loaded', () => {
    render(<Player />);
    expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
  });

  it('should render the current track title when one is loaded', () => {
    render(<Player />, {
      preloadedState: {
        player: { currentTrack: mockTrack } as never,
      },
    });
    expect(screen.getByText('Test Track')).toBeInTheDocument();
  });

  it('should render the previous and next track buttons', () => {
    render(<Player />, {
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
    mockPlayEnhanced.mockClear();
    render(<Player />, {
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

  it('should render the queue panel toggle', () => {
    render(<Player />);
    // QueuePanel toggle is rendered as part of the right-side action group.
    // Looser query because the exact aria label can drift; the absence of
    // the queue toggle would be a structural regression worth catching.
    const queueButton =
      screen.queryByRole('button', { name: /queue/i }) ||
      screen.queryByTestId?.('queue-toggle');
    expect(queueButton).toBeTruthy();
  });
});
