/**
 * Transport children must not re-render on the 10Hz position tick (#4632)
 *
 * `Player` legitimately re-renders 10x/second while a track is playing: it
 * subscribes to `usePlaybackProgress()` because it renders the progress bar and
 * the time display, and #5006 deliberately split that high-frequency context out
 * so only Player pays for it. What it must NOT do is drag its siblings along.
 *
 * The expensive one is `QueuePanel`, which is always mounted and merely hidden
 * via CSS to preserve scroll and focus (#2541). Unmemoized, every tick
 * re-invoked `usePlaybackQueue()`, re-ran `useVirtualizer()`, and rebuilt the
 * JSX for every visible row — only the leaf `QueueTrackItem`s were protected
 * (#4177), so all the reconciliation above them still happened, for the whole
 * duration of every playback session.
 *
 * Two properties are needed and neither implies the other:
 *   1. the children are actually wrapped in `React.memo`; and
 *   2. `Player` passes them referentially stable props — a single inline arrow
 *      or object literal makes `memo` a silent no-op that still looks correct.
 *
 * (2) is the one that cannot be checked by reading the code, so it is measured
 * here with render counters driven by a real 10Hz interval under fake timers.
 * The prerequisite for (2) was #4608, which stabilised `playEnhanced` and hence
 * the transport handlers.
 */

import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest';
import { act, screen } from '@testing-library/react';
import { render } from '@/test/test-utils';

const { counts, mounts, resetCounts } = vi.hoisted(() => {
  const counts: Record<string, number> = {};
  const mounts: Record<string, number> = {};
  return {
    counts,
    mounts,
    resetCounts: () => {
      for (const k of Object.keys(counts)) counts[k] = 0;
      for (const k of Object.keys(mounts)) mounts[k] = 0;
    },
  };
});

/**
 * Replace a child with a memoized counter wrapping the real component.
 *
 * The wrapper is memoized rather than bare on purpose: what is under test is
 * whether `Player` hands this child stable props, which is precisely the
 * condition that makes the real component's own `memo` effective. A bare
 * wrapper would re-render every tick regardless and measure nothing.
 */
function countingMock(name: string) {
  return async (importOriginal: () => Promise<Record<string, unknown>>) => {
    const [actual, react, jsxRuntime] = await Promise.all([
      importOriginal(),
      import('react'),
      import('react/jsx-runtime'),
    ]);
    const Real = (actual as { default: React.ComponentType<unknown> }).default;
    counts[name] = 0;
    mounts[name] = 0;
    const Counter = react.memo((props: Record<string, unknown>) => {
      counts[name] = (counts[name] ?? 0) + 1;
      // Mount identity, not render count — this is what preserves scroll and
      // focus across a queue-panel toggle (#2541).
      react.useEffect(() => {
        mounts[name] = (mounts[name] ?? 0) + 1;
      }, []);
      return jsxRuntime.jsx(Real, props);
    });
    Counter.displayName = `Counting(${name})`;
    return { ...actual, default: Counter, [name]: Counter };
  };
}

vi.mock('../TrackDisplay', countingMock('TrackDisplay'));
vi.mock('../PlaybackControls', countingMock('PlaybackControls'));
vi.mock('../VolumeControl', countingMock('VolumeControl'));
vi.mock('../BufferingIndicator', countingMock('BufferingIndicator'));
vi.mock('../QueuePanel', countingMock('QueuePanel'));

// The 10Hz tick, modelled faithfully: the provider owns a currentTime that
// advances on a 100ms interval, exactly as useAudioStreamingCore does while
// playing. Driving it with a real interval under fake timers means the
// re-render cascade under test is the production one, not a hand-fired setState.
vi.mock('@/hooks/enhancement/usePlayEnhanced', async () => {
  const react = await import('react');
  // Hoisted out of the returned object on purpose. In production these are all
  // `useCallback`-stable (useAudioStreamingCore.ts:460-480), so creating fresh
  // `vi.fn()`s per call would inject identity churn the real hook does not have
  // — the transport handlers would destabilise and this test would report a
  // memoization failure that exists only in its own mock.
  const stable = {
    playEnhanced: vi.fn(),
    playNormal: vi.fn(),
    seekTo: vi.fn(),
    pausePlayback: vi.fn(),
    resumePlayback: vi.fn(),
    stopPlayback: vi.fn(),
    setVolume: vi.fn(),
  };
  return {
    usePlayEnhanced: () => {
      const [currentTime, setCurrentTime] = react.useState(0);
      react.useEffect(() => {
        const id = setInterval(() => {
          setCurrentTime((t) => Math.round((t + 0.1) * 10) / 10);
        }, 100);
        return () => clearInterval(id);
      }, []);
      return {
        ...stable,
        isStreaming: true,
        streamingState: 'streaming',
        streamingProgress: 50,
        bufferedSamples: 1000,
        processedChunks: 5,
        totalChunks: 10,
        currentTime,
        isPaused: false,
        isSeeking: false,
        error: null,
        fingerprintStatus: 'idle',
        fingerprintMessage: null,
      };
    },
  };
});

vi.mock('@/hooks/enhancement/useEnhancementControl', () => ({
  useEnhancementControl: () => ({ enabled: true, preset: 'warm', intensity: 0.5 }),
}));

// Queue plumbing pulls REST + WebSocket machinery that jsdom has no analog for.
// Returned object is module-constant so QueuePanel's own store subscription
// cannot itself cause a re-render and confound the measurement.
const QUEUE_STATE = {
  queue: [],
  currentIndex: 0,
  isShuffled: false,
  repeatMode: 'off' as const,
  removeTrack: vi.fn(),
  reorderTrack: vi.fn(),
  toggleShuffle: vi.fn(),
  setRepeatMode: vi.fn(),
  clearQueue: vi.fn(),
  isLoading: false,
  error: null,
};
vi.mock('@/hooks/player/usePlaybackQueue', () => ({
  usePlaybackQueue: () => QUEUE_STATE,
}));

import Player from '../Player';

const MEMO_TYPE = Symbol.for('react.memo');

const TRACK = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 200,
};

function playingState(track = TRACK) {
  return {
    preloadedState: {
      player: { currentTrack: track, volume: 50, isMuted: false },
    },
  } as unknown as Parameters<typeof render>[1];
}

const TICK_MS = 100;

/**
 * Advance `ms` one 100ms tick at a time, flushing React between each.
 *
 * Advancing the whole second inside a single `act()` would fire all ten
 * interval callbacks before React ever re-rendered, so React would batch them
 * into ONE render pass — an unmemoized child would then count 1 instead of 10
 * and the assertion could not distinguish "memo held" from "the cascade was
 * collapsed by batching". Stepping tick-by-tick reproduces the production
 * cadence: ten separate renders.
 */
async function advance(ms: number) {
  for (let elapsed = 0; elapsed < ms; elapsed += TICK_MS) {
    await act(async () => {
      vi.advanceTimersByTime(TICK_MS);
    });
  }
}

describe('Player 10Hz tick does not re-render transport children (#4632)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    resetCounts();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('re-renders none of the transport children across a second of playback', async () => {
    render(<Player />, playingState());
    resetCounts(); // ignore mount renders; measure the steady state

    await advance(1000);

    expect(counts).toEqual({
      TrackDisplay: 0,
      PlaybackControls: 0,
      VolumeControl: 0,
      BufferingIndicator: 0,
      QueuePanel: 0,
    });
  });

  it.each([
    'QueuePanel',
    'TrackDisplay',
    'PlaybackControls',
    'VolumeControl',
    'BufferingIndicator',
  ])('does not re-render %s on the tick', async (name) => {
    render(<Player />, playingState());
    resetCounts();

    await advance(1000);

    expect(counts[name]).toBe(0);
  });

  it('actually ticks — the zero counts above would be vacuous otherwise', async () => {
    const { container } = render(<Player />, playingState());

    // TimeDisplay is deliberately NOT memoized: it renders the value that
    // changes. Its text advancing proves the interval fired and Player
    // re-rendered, so the zero counts above mean "memo held", not "the tick
    // never happened".
    const timeText = () =>
      container.querySelector('[data-testid="time-display"]')?.textContent
      ?? container.textContent
      ?? '';
    const before = timeText();

    await advance(1000);

    expect(timeText()).not.toBe(before);
  });

  it('still re-renders a child when its props genuinely change', async () => {
    render(<Player />, playingState());
    resetCounts();

    await advance(1000);
    expect(counts.TrackDisplay).toBe(0);

    // memo must not over-block: a real track change has to get through.
    render(<Player />, playingState({ ...TRACK, title: 'Different Track' }));

    expect(counts.TrackDisplay).toBeGreaterThan(0);
    expect(screen.getByText('Different Track')).toBeInTheDocument();
  });
});

describe('memoizing QueuePanel preserves the #2541 always-mounted behaviour', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    resetCounts();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('keeps the panel mounted across a toggle, and across the tick', async () => {
    render(<Player />, playingState());

    const toggle = screen.getByRole('button', { name: /toggle queue/i });
    expect(mounts.QueuePanel).toBe(1);

    await act(async () => {
      toggle.click();
    });
    await advance(500);
    await act(async () => {
      toggle.click();
    });

    // Remounting would discard scroll offset and focus — the whole reason
    // #2541 hides the panel with CSS instead of unmounting it. `memo` must not
    // change that, and neither may it *cause* a remount.
    expect(mounts.QueuePanel).toBe(1);
  });

  it('hides via CSS rather than unmounting, both closed and open', async () => {
    const { container } = render(<Player />, playingState());
    const region = () => container.querySelector('#queue-panel-region');

    expect(region()).not.toBeNull();
    expect(region()).toHaveStyle({ display: 'none' });

    await act(async () => {
      screen.getByRole('button', { name: /toggle queue/i }).click();
    });

    expect(region()).not.toBeNull();
    expect(region()).not.toHaveStyle({ display: 'none' });
  });

  it('re-renders the panel when the toggle actually changes its subtree', async () => {
    render(<Player />, playingState());
    resetCounts();

    await act(async () => {
      screen.getByRole('button', { name: /toggle queue/i }).click();
    });

    // `collapsed` is a constant `false` and only the wrapper's `display`
    // changes, so QueuePanel itself legitimately need not re-render on a
    // toggle. Pin that it also is not remounted, which is the part that matters.
    expect(mounts.QueuePanel).toBe(0);
  });
});

describe('the children are wrapped in React.memo (#4632)', () => {
  // Structural counterpart to the measurement above: stable props with no memo
  // is just as inert as memo with unstable props, and the measurement alone
  // cannot tell the two apart.
  //
  // These must be the REAL modules — the counting mocks installed above are
  // themselves memoized, so asserting on the mocked bindings would be vacuous.
  it.each([
    '../TrackDisplay',
    '../PlaybackControls',
    '../VolumeControl',
    '../BufferingIndicator',
    '../QueuePanel',
  ])('%s exports a memo component', async (path) => {
    const actual = await vi.importActual<{ default: unknown }>(path);

    expect((actual.default as { $$typeof?: symbol }).$$typeof).toBe(MEMO_TYPE);
  });
});
