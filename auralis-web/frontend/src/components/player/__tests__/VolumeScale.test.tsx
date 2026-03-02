/**
 * Volume Scale Consistency Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests for issue #2116: Volume scale inconsistency (0-100 in Redux vs 0-1 in engine)
 *
 * Verifies:
 * - Volume is correctly stored as 0-100 in Redux
 * - Volume is correctly converted to 0-1 for VolumeControl component
 * - Volume changes are persisted to Redux
 * - AudioPlaybackEngine receives correct 0-1 scale
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import Player from '../Player';
import playerReducer from '@/store/slices/playerSlice';
import queueReducer from '@/store/slices/queueSlice';

// Mock WebSocket context
vi.mock('@/contexts/WebSocketContext', () => ({
  useWebSocketContext: () => ({
    subscribe: vi.fn(() => vi.fn()),
    send: vi.fn(),
  }),
}));

// Mock usePlayEnhanced hook
const mockSetVolume = vi.fn();
vi.mock('@/hooks/enhancement/usePlayEnhanced', () => ({
  usePlayEnhanced: () => ({
    playEnhanced: vi.fn(),
    seekTo: vi.fn(),
    pausePlayback: vi.fn(),
    resumePlayback: vi.fn(),
    stopPlayback: vi.fn(),
    setVolume: mockSetVolume,
    isStreaming: false,
    streamingState: 'idle',
    processedChunks: 0,
    totalChunks: 0,
    currentTime: 0,
    isPaused: false,
    isSeeking: false,
    error: null,
  }),
}));

describe('Player - Volume Scale Consistency (#2116)', () => {
  let store: any;

  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks();

    // Create fresh store with initial volume
    store = configureStore({
      reducer: {
        player: playerReducer,
        queue: queueReducer,
      } as any,
      preloadedState: {
        player: {
          currentTrack: {
            id: 1,
            title: 'Test Track',
            artist: 'Test Artist',
            album: 'Test Album',
            duration: 180,
          },
          isPlaying: false,
          currentTime: 0,
          duration: 180,
          volume: 70, // 0-100 scale in Redux
          isMuted: false,
          preset: 'adaptive',
          lastUpdated: Date.now(),
        },
        queue: {
          tracks: [],
          currentIndex: 0,
          shuffle: false,
          repeat: 'none',
        },
      } as any,
    });
  });

  it('should store volume as 0-100 in Redux', () => {
    const state = store.getState();
    expect(state.player.volume).toBe(70);
  });

  it('should convert volume to 0-1 for VolumeControl component', () => {
    render(
      <Provider store={store}>
        <Player />
      </Provider>
    );

    const volumeSlider = screen.getByTestId('volume-control-slider') as HTMLInputElement;

    // Redux stores 70, so slider should show 0.7 (70/100)
    expect(parseFloat(volumeSlider.value)).toBeCloseTo(0.7, 2);
  });

  it('should display volume percentage correctly', () => {
    render(
      <Provider store={store}>
        <Player />
      </Provider>
    );

    const volumePercentage = screen.getByTestId('volume-control-percentage');

    // Should display "70%"
    expect(volumePercentage.textContent).toBe('70%');
  });

  it('should persist volume changes to Redux when slider changes', () => {
    render(
      <Provider store={store}>
        <Player />
      </Provider>
    );

    const volumeSlider = screen.getByTestId('volume-control-slider') as HTMLInputElement;

    // Change volume to 0.5 (50%)
    fireEvent.change(volumeSlider, { target: { value: '0.5' } });

    // Redux should now store 50 (0-100 scale)
    const state = store.getState();
    expect(state.player.volume).toBe(50);
  });

  it('should call AudioPlaybackEngine.setVolume with 0-1 scale', () => {
    render(
      <Provider store={store}>
        <Player />
      </Provider>
    );

    const volumeSlider = screen.getByTestId('volume-control-slider') as HTMLInputElement;

    // Change volume to 0.8 (80%)
    fireEvent.change(volumeSlider, { target: { value: '0.8' } });

    // setVolume should be called with 0.8 (0-1 scale)
    expect(mockSetVolume).toHaveBeenCalledWith(0.8);
  });

  it('should handle volume changes at boundary values', () => {
    render(
      <Provider store={store}>
        <Player />
      </Provider>
    );

    const volumeSlider = screen.getByTestId('volume-control-slider') as HTMLInputElement;

    // Test minimum (0)
    fireEvent.change(volumeSlider, { target: { value: '0' } });
    expect(store.getState().player.volume).toBe(0);
    expect(mockSetVolume).toHaveBeenCalledWith(0);

    // Test maximum (1.0)
    fireEvent.change(volumeSlider, { target: { value: '1' } });
    expect(store.getState().player.volume).toBe(100);
    expect(mockSetVolume).toHaveBeenCalledWith(1);
  });

  it('should round volume correctly when converting 0-1 to 0-100', () => {
    render(
      <Provider store={store}>
        <Player />
      </Provider>
    );

    const volumeSlider = screen.getByTestId('volume-control-slider') as HTMLInputElement;

    // Test rounding: 0.754 should round to 75 (not 75.4)
    fireEvent.change(volumeSlider, { target: { value: '0.754' } });
    expect(store.getState().player.volume).toBe(75);

    // Test rounding: 0.755 should round to 76
    fireEvent.change(volumeSlider, { target: { value: '0.756' } });
    expect(store.getState().player.volume).toBe(76);
  });

  it('should maintain volume consistency after WebSocket player_state update', async () => {
    // This test verifies that when backend sends player_state with volume=80,
    // Redux is updated correctly and VolumeControl displays the right value

    const { rerender } = render(
      <Provider store={store}>
        <Player />
      </Provider>
    );

    // Simulate WebSocket update (backend sends volume as 0-100)
    store.dispatch({ type: 'player/setVolume', payload: 85 });

    // Redux should store 85
    expect(store.getState().player.volume).toBe(85);

    // Force re-render to pick up Redux state change
    rerender(
      <Provider store={store}>
        <Player />
      </Provider>
    );

    // VolumeControl slider should show 0.85
    const volumeSlider = screen.getByTestId('volume-control-slider') as HTMLInputElement;
    expect(parseFloat(volumeSlider.value)).toBeCloseTo(0.85, 2);

    // VolumeControl percentage should show "85%"
    const volumePercentage = screen.getByTestId('volume-control-percentage');
    expect(volumePercentage.textContent).toBe('85%');
  });
});
