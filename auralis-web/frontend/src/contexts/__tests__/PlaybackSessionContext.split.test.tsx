/**
 * PlaybackSessionContext split: usePlaybackControls / usePlaybackProgress (#5006)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Before this fix, one combined `usePlaybackSession()` value bundled the
 * 10Hz `currentTime` field with low-frequency handlers/booleans in a single
 * `useMemo`, so every consumer — including the app root — re-rendered on
 * every position tick regardless of which fields it actually read.
 *
 * This asserts the two split hooks actually decouple re-renders: a
 * `usePlaybackControls()`-only consumer must NOT re-render when only
 * `currentTime` changes, and a `usePlaybackProgress()` consumer must.
 */

import { describe, it, expect, vi } from 'vitest';
import { memo } from 'react';
import { render } from '@/test/test-utils';
import { usePlaybackControls, usePlaybackProgress } from '@/contexts/PlaybackSessionContext';

const { mockUsePlayEnhanced } = vi.hoisted(() => ({
  mockUsePlayEnhanced: vi.fn(),
}));

vi.mock('@/hooks/enhancement/usePlayEnhanced', () => ({
  usePlayEnhanced: () => mockUsePlayEnhanced(),
}));

vi.mock('@/hooks/enhancement/useEnhancementControl', () => ({
  useEnhancementControl: () => ({ enabled: false, preset: 'adaptive', intensity: 1.0 }),
}));

const baseSession = {
  playEnhanced: vi.fn(),
  playNormal: vi.fn(),
  seekTo: vi.fn(),
  pausePlayback: vi.fn(),
  resumePlayback: vi.fn(),
  stopPlayback: vi.fn(),
  setVolume: vi.fn(),
  isStreaming: true,
  streamingState: 'streaming' as const,
  processedChunks: 0,
  totalChunks: 10,
  isPaused: false,
  isSeeking: false,
  error: null,
};

// Memoized with no changing props — will only re-render in response to a
// context value change, not because a parent element was re-created by
// `rerender()`. This is what makes the render-count assertions meaningful.
const ControlsConsumer = memo(function ControlsConsumer({ onRender }: { onRender: () => void }) {
  onRender();
  usePlaybackControls();
  return null;
});

const ProgressConsumer = memo(function ProgressConsumer({ onRender }: { onRender: () => void }) {
  onRender();
  usePlaybackProgress();
  return null;
});

describe('#5006: PlaybackSessionContext split re-render isolation', () => {
  it('a usePlaybackControls()-only consumer does not re-render when only currentTime changes', () => {
    const controlsRenderSpy = vi.fn();
    const progressRenderSpy = vi.fn();

    mockUsePlayEnhanced.mockReturnValue({ ...baseSession, currentTime: 0 });

    const { rerender } = render(
      <>
        <ControlsConsumer onRender={controlsRenderSpy} />
        <ProgressConsumer onRender={progressRenderSpy} />
      </>
    );

    expect(controlsRenderSpy).toHaveBeenCalledTimes(1);
    expect(progressRenderSpy).toHaveBeenCalledTimes(1);

    // Simulate a 10Hz position tick: only currentTime changes, nothing else.
    mockUsePlayEnhanced.mockReturnValue({ ...baseSession, currentTime: 1.5 });
    rerender(
      <>
        <ControlsConsumer onRender={controlsRenderSpy} />
        <ProgressConsumer onRender={progressRenderSpy} />
      </>
    );

    expect(progressRenderSpy).toHaveBeenCalledTimes(2);
    // The bug this fix closes: before the split, this would also be 2.
    expect(controlsRenderSpy).toHaveBeenCalledTimes(1);
  });

  it('a usePlaybackControls() consumer DOES re-render when a controls field changes', () => {
    const controlsRenderSpy = vi.fn();
    const progressRenderSpy = vi.fn();

    mockUsePlayEnhanced.mockReturnValue({ ...baseSession, currentTime: 0, isPaused: false });

    const { rerender } = render(
      <>
        <ControlsConsumer onRender={controlsRenderSpy} />
        <ProgressConsumer onRender={progressRenderSpy} />
      </>
    );
    expect(controlsRenderSpy).toHaveBeenCalledTimes(1);

    mockUsePlayEnhanced.mockReturnValue({ ...baseSession, currentTime: 0, isPaused: true });
    rerender(
      <>
        <ControlsConsumer onRender={controlsRenderSpy} />
        <ProgressConsumer onRender={progressRenderSpy} />
      </>
    );

    expect(controlsRenderSpy).toHaveBeenCalledTimes(2);
  });
});
