/**
 * useEnhancedPlaybackShortcuts Hook Tests
 *
 * Tests for keyboard shortcuts controlling enhanced audio playback.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { configureStore } from '@reduxjs/toolkit';
import { Provider } from 'react-redux';
import playerReducer, { type PresetName } from '@/store/slices/playerSlice';
import queueReducer from '@/store/slices/queueSlice';
import cacheReducer from '@/store/slices/cacheSlice';
import connectionReducer from '@/store/slices/connectionSlice';
import { useEnhancedPlaybackShortcuts } from '../useEnhancedPlaybackShortcuts';
import type React from 'react';

const DEFAULT_STREAMING = {
  normal: {
    state: 'idle' as const,
    trackId: null,
    intensity: 1.0,
    progress: 0,
    bufferedSamples: 0,
    totalChunks: 0,
    processedChunks: 0,
    error: null,
  },
  enhanced: {
    state: 'streaming' as const,
    trackId: 1,
    intensity: 0.5,
    progress: 50,
    bufferedSamples: 44100,
    totalChunks: 10,
    processedChunks: 5,
    error: null,
  },
};

function createStore(overrides: Record<string, any> = {}) {
  return configureStore({
    reducer: {
      player: playerReducer,
      queue: queueReducer,
      cache: cacheReducer,
      connection: connectionReducer,
    },
    preloadedState: {
      player: {
        isPlaying: false,
        currentTrack: null,
        currentTime: 0,
        duration: 0,
        volume: 80,
        isMuted: false,
        preset: 'adaptive' as PresetName,
        isLoading: false,
        error: null,
        lastUpdated: 0,
        streaming: DEFAULT_STREAMING,
        ...overrides,
      },
    },
  });
}

function createWrapper(store: ReturnType<typeof createStore>) {
  return ({ children }: { children: React.ReactNode }) =>
    Provider({ store, children });
}

function fireKeyDown(opts: Partial<KeyboardEvent> = {}) {
  const event = new KeyboardEvent('keydown', {
    bubbles: true,
    cancelable: true,
    ...opts,
  });
  window.dispatchEvent(event);
  return event;
}

describe('useEnhancedPlaybackShortcuts', () => {
  let store: ReturnType<typeof createStore>;

  beforeEach(() => {
    store = createStore();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initial state', () => {
    it('returns current playback state from Redux', () => {
      const { result } = renderHook(
        () => useEnhancedPlaybackShortcuts({ trackId: 1, enabled: true }),
        { wrapper: createWrapper(store) }
      );

      expect(result.current.isEnabled).toBe(true);
      expect(result.current.currentPreset).toBe('adaptive');
      expect(result.current.currentIntensity).toBe(0.5);
      expect(result.current.isEnhancedMode).toBe(true);
    });

    it('defaults to enabled when no config provided', () => {
      const { result } = renderHook(
        () => useEnhancedPlaybackShortcuts(),
        { wrapper: createWrapper(store) }
      );

      expect(result.current.isEnabled).toBe(true);
    });
  });

  describe('Shift+E: toggle enhanced mode', () => {
    it('calls onEnhancedToggle with negated state', () => {
      const onEnhancedToggle = vi.fn();

      renderHook(
        () => useEnhancedPlaybackShortcuts({ trackId: 1, onEnhancedToggle }),
        { wrapper: createWrapper(store) }
      );

      fireKeyDown({ key: 'E', shiftKey: true });

      // isEnhancedMode is true (streaming state), so toggle should pass false
      expect(onEnhancedToggle).toHaveBeenCalledWith(false);
    });
  });

  describe('preset shortcuts', () => {
    it.each([
      ['a', 'adaptive'],
      ['s', 'gentle'],
      ['w', 'warm'],
      ['b', 'bright'],
      ['p', 'punchy'],
    ] as const)('Shift+%s selects %s preset', (key, preset) => {
      const onPresetChange = vi.fn();

      renderHook(
        () => useEnhancedPlaybackShortcuts({ trackId: 1, onPresetChange }),
        { wrapper: createWrapper(store) }
      );

      fireKeyDown({ key: key.toUpperCase(), shiftKey: true });

      expect(onPresetChange).toHaveBeenCalledWith(preset);
    });
  });

  describe('intensity shortcuts', () => {
    it('Shift+ArrowUp increases intensity by 0.1', () => {
      const onIntensityChange = vi.fn();

      renderHook(
        () => useEnhancedPlaybackShortcuts({ trackId: 1, onIntensityChange }),
        { wrapper: createWrapper(store) }
      );

      fireKeyDown({ key: 'ArrowUp', shiftKey: true });

      // Current intensity is 0.5, so expect ~0.6
      expect(onIntensityChange).toHaveBeenCalledWith(
        expect.closeTo(0.6, 5)
      );
    });

    it('Shift+ArrowDown decreases intensity by 0.1', () => {
      const onIntensityChange = vi.fn();

      renderHook(
        () => useEnhancedPlaybackShortcuts({ trackId: 1, onIntensityChange }),
        { wrapper: createWrapper(store) }
      );

      fireKeyDown({ key: 'ArrowDown', shiftKey: true });

      expect(onIntensityChange).toHaveBeenCalledWith(
        expect.closeTo(0.4, 5)
      );
    });

    it('clamps intensity at 1.0 maximum', () => {
      const highStore = createStore({
        streaming: {
          normal: { state: 'idle', trackId: null, intensity: 1.0, progress: 0, bufferedSamples: 0, totalChunks: 0, processedChunks: 0, error: null },
          enhanced: { state: 'streaming', trackId: 1, intensity: 0.95, progress: 50, bufferedSamples: 0, totalChunks: 0, processedChunks: 0, error: null },
        },
      });

      const onIntensityChange = vi.fn();

      renderHook(
        () => useEnhancedPlaybackShortcuts({ trackId: 1, onIntensityChange }),
        { wrapper: createWrapper(highStore) }
      );

      fireKeyDown({ key: 'ArrowUp', shiftKey: true });

      expect(onIntensityChange).toHaveBeenCalledWith(1.0);
    });

    it('clamps intensity at 0.0 minimum', () => {
      const lowStore = createStore({
        streaming: {
          normal: { state: 'idle', trackId: null, intensity: 1.0, progress: 0, bufferedSamples: 0, totalChunks: 0, processedChunks: 0, error: null },
          enhanced: { state: 'streaming', trackId: 1, intensity: 0.05, progress: 50, bufferedSamples: 0, totalChunks: 0, processedChunks: 0, error: null },
        },
      });

      const onIntensityChange = vi.fn();

      renderHook(
        () => useEnhancedPlaybackShortcuts({ trackId: 1, onIntensityChange }),
        { wrapper: createWrapper(lowStore) }
      );

      fireKeyDown({ key: 'ArrowDown', shiftKey: true });

      expect(onIntensityChange).toHaveBeenCalledWith(0.0);
    });
  });

  describe('guard conditions', () => {
    it('ignores shortcuts when enabled=false', () => {
      const onPresetChange = vi.fn();

      renderHook(
        () => useEnhancedPlaybackShortcuts({ trackId: 1, enabled: false, onPresetChange }),
        { wrapper: createWrapper(store) }
      );

      fireKeyDown({ key: 'A', shiftKey: true });

      expect(onPresetChange).not.toHaveBeenCalled();
    });

    it('ignores shortcuts when no trackId', () => {
      const onPresetChange = vi.fn();

      renderHook(
        () => useEnhancedPlaybackShortcuts({ enabled: true, onPresetChange }),
        { wrapper: createWrapper(store) }
      );

      fireKeyDown({ key: 'A', shiftKey: true });

      expect(onPresetChange).not.toHaveBeenCalled();
    });

    it('ignores non-Shift key events', () => {
      const onPresetChange = vi.fn();

      renderHook(
        () => useEnhancedPlaybackShortcuts({ trackId: 1, onPresetChange }),
        { wrapper: createWrapper(store) }
      );

      fireKeyDown({ key: 'a', shiftKey: false });

      expect(onPresetChange).not.toHaveBeenCalled();
    });
  });

  describe('cleanup', () => {
    it('removes event listener on unmount', () => {
      const spy = vi.spyOn(window, 'removeEventListener');

      const { unmount } = renderHook(
        () => useEnhancedPlaybackShortcuts({ trackId: 1 }),
        { wrapper: createWrapper(store) }
      );

      unmount();

      expect(spy).toHaveBeenCalledWith('keydown', expect.any(Function));
    });
  });
});
