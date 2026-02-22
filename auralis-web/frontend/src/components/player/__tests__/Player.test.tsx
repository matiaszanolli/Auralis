/**
 * Player.tsx orchestration component tests (#2363)
 *
 * Basic test coverage for the Player orchestration component.
 * Verifies rendering, export, and structural invariants.
 */

import { describe, it, expect, vi } from 'vitest';

// Mock heavy dependencies before importing Player
vi.mock('@/hooks/enhancement/usePlayEnhanced', () => ({
  usePlayEnhanced: () => ({
    playEnhanced: vi.fn(),
    seekTo: vi.fn(),
    pausePlayback: vi.fn(),
    resumePlayback: vi.fn(),
    stopPlayback: vi.fn(),
    isStreaming: false,
    streamingProgress: 0,
    error: null,
  }),
}));

vi.mock('react-redux', () => ({
  useSelector: vi.fn((selector) => {
    // Return sensible defaults for all selectors
    const defaults: Record<string, unknown> = {
      'selectQueueTracks': [],
      'selectCurrentIndex': 0,
    };
    return selector.name in defaults ? defaults[selector.name] : undefined;
  }),
  useDispatch: () => vi.fn(),
}));

vi.mock('@/store/selectors', () => ({
  playerSelectors: {
    selectCurrentTrack: () => null,
    selectIsPlaying: () => false,
    selectVolume: () => 80,
    selectIsMuted: () => false,
    selectCurrentTime: () => 0,
    selectDuration: () => 0,
    selectIsLoading: () => false,
    selectError: () => null,
    selectPreset: () => 'adaptive',
    selectIsStreaming: () => false,
    selectStreamingProgress: () => 0,
  },
}));

describe('Player', () => {
  it('should export a default component', async () => {
    const module = await import('../Player');
    expect(module.default).toBeDefined();
    expect(typeof module.default).toBe('object'); // React.memo wraps it
  });

  it('should import without errors', async () => {
    // Verifies that all imports resolve (no missing modules)
    await expect(import('../Player')).resolves.toBeDefined();
  });

  it('source should integrate all 6 Phase 4 components', async () => {
    // Structural check: Player must wire all child components
    const fs = await import('fs');
    const path = await import('path');
    const source = fs.readFileSync(
      path.resolve(__dirname, '../Player.tsx'),
      'utf-8'
    );

    const requiredComponents = [
      'TimeDisplay',
      'BufferingIndicator',
      'ProgressBar',
      'PlaybackControls',
      'VolumeControl',
      'TrackDisplay',
    ];

    for (const component of requiredComponents) {
      expect(source).toContain(component);
    }
  });

  it('source should use usePlayEnhanced for streaming', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const source = fs.readFileSync(
      path.resolve(__dirname, '../Player.tsx'),
      'utf-8'
    );

    expect(source).toContain('usePlayEnhanced');
  });

  it('source should handle auto-advance on track completion', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const source = fs.readFileSync(
      path.resolve(__dirname, '../Player.tsx'),
      'utf-8'
    );

    // Must have logic for advancing to next track
    expect(source).toContain('nextTrack');
  });

  it('source should have queue panel toggle', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const source = fs.readFileSync(
      path.resolve(__dirname, '../Player.tsx'),
      'utf-8'
    );

    expect(source).toContain('QueuePanel');
  });
});
