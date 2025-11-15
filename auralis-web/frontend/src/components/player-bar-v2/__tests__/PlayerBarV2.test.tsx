/**
 * PlayerBarV2 Component Tests
 *
 * Tests the new player bar v2 component with:
 * - Playback controls (play, pause, next, prev)
 * - Volume control
 * - Enhancement toggle
 * - Progress bar
 * - Track info display
 */

import { vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { PlayerBarV2 } from '../PlayerBarV2';

// Mock sub-components to isolate PlayerBarV2 logic
vi.mock('../TrackInfo', () => ({
  TrackInfo: ({ track }: any) => (
    <div data-testid="track-info">
      {track ? (
        <>
          <span>{track.title}</span>
          <span>{track.artist}</span>
        </>
      ) : (
        <span>No Track</span>
      )}
    </div>
  ),
}));

vi.mock('../PlaybackControls', () => ({
  PlaybackControls: ({ isPlaying, onPlayPause, onPrevious, onNext }: any) => (
    <div data-testid="playback-controls">
      <button onClick={onPlayPause}>{isPlaying ? 'Pause' : 'Play'}</button>
      <button onClick={onPrevious}>Prev</button>
      <button onClick={onNext}>Next</button>
    </div>
  ),
}));

vi.mock('../ProgressBar', () => ({
  ProgressBar: ({ currentTime, duration, onSeek }: any) => (
    <div data-testid="progress-bar">
      <span>{Math.floor(currentTime / 60)}:{String(currentTime % 60).padStart(2, '0')}</span>
      <input
        type="range"
        data-testid="progress-slider"
        onChange={(e) => onSeek(parseInt(e.target.value))}
      />
      <span>{Math.floor(duration / 60)}:{String(duration % 60).padStart(2, '0')}</span>
    </div>
  ),
}));

vi.mock('../VolumeControl', () => ({
  VolumeControl: ({ volume, onChange }: any) => (
    <div data-testid="volume-control">
      <span>{volume}</span>
      <input
        type="range"
        data-testid="volume-slider"
        value={volume}
        onChange={(e) => onChange(parseInt(e.target.value))}
      />
    </div>
  ),
}));

vi.mock('../EnhancementToggle', () => ({
  EnhancementToggle: ({ isEnabled, onToggle }: any) => (
    <button data-testid="enhancement-toggle" onClick={onToggle}>
      {isEnabled ? 'Enhancement On' : 'Enhancement Off'}
    </button>
  ),
}));

// Hoisted mock data for consistency
const mockPlayer = {
  currentTrack: {
    id: 1,
    title: 'Test Track',
    artist: 'Test Artist',
    duration: 180,
  },
  isPlaying: false,
  currentTime: 0,
  duration: 180,
  volume: 100,
  isEnhanced: false,
  queue: [
    { id: 1, title: 'Track 1' },
    { id: 2, title: 'Track 2' },
  ],
  queueIndex: 0,
};

const mockHandlers = {
  onPlay: vi.fn(),
  onPause: vi.fn(),
  onSeek: vi.fn(),
  onVolumeChange: vi.fn(),
  onEnhancementToggle: vi.fn(),
  onPrevious: vi.fn(),
  onNext: vi.fn(),
};


describe('PlayerBarV2', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render player bar container', () => {
      render(
        <PlayerBarV2
          player={mockPlayer}
          {...mockHandlers}
        />
      );
      expect(screen.getByTestId('track-info')).toBeInTheDocument();
      expect(screen.getByTestId('playback-controls')).toBeInTheDocument();
      expect(screen.getByTestId('progress-bar')).toBeInTheDocument();
      expect(screen.getByTestId('volume-control')).toBeInTheDocument();
      expect(screen.getByTestId('enhancement-toggle')).toBeInTheDocument();
    });

    it('should render playback controls', () => {
      render(
        <PlayerBarV2
          player={mockPlayer}
          {...mockHandlers}
        />
      );
      expect(screen.getByTestId('playback-controls')).toBeInTheDocument();
    });

    it('should display track info', () => {
      render(
        <PlayerBarV2
          player={mockPlayer}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('Test Track')).toBeInTheDocument();
      expect(screen.getByText('Test Artist')).toBeInTheDocument();
    });

    it('should render volume control slider', () => {
      render(
        <PlayerBarV2
          player={mockPlayer}
          {...mockHandlers}
        />
      );
      const volumeSlider = screen.getByTestId('volume-slider');
      expect(volumeSlider).toBeInTheDocument();
    });

    it('should render enhancement toggle', () => {
      render(
        <PlayerBarV2
          player={mockPlayer}
          {...mockHandlers}
        />
      );
      const toggleButton = screen.getByTestId('enhancement-toggle');
      expect(toggleButton).toBeInTheDocument();
    });

    it('should render progress bar', () => {
      render(
        <PlayerBarV2
          player={mockPlayer}
          {...mockHandlers}
        />
      );
      expect(screen.getByTestId('progress-bar')).toBeInTheDocument();
    });
  });

  describe('Playback Controls', () => {
    it('should show play button when paused', () => {
      render(
        <PlayerBarV2
          player={{ ...mockPlayer, isPlaying: false }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('Play')).toBeInTheDocument();
    });

    it('should show pause button when playing', () => {
      render(
        <PlayerBarV2
          player={{ ...mockPlayer, isPlaying: true }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('Pause')).toBeInTheDocument();
    });

    it('should call play/pause on button click', async () => {
      const user = userEvent.setup();
      const { rerender } = render(
        <PlayerBarV2
          player={{ ...mockPlayer, isPlaying: false }}
          {...mockHandlers}
        />
      );
      const playButton = screen.getByText('Play');
      await user.click(playButton);
      expect(mockHandlers.onPlay).toHaveBeenCalled();

      // Update for pause state
      rerender(
        <PlayerBarV2
          player={{ ...mockPlayer, isPlaying: true }}
          {...mockHandlers}
        />
      );
      const pauseButton = screen.getByText('Pause');
      await user.click(pauseButton);
      expect(mockHandlers.onPause).toHaveBeenCalled();
    });

    it('should call next on next button click', async () => {
      const user = userEvent.setup();
      render(
        <PlayerBarV2
          player={mockPlayer}
          {...mockHandlers}
        />
      );
      const nextButton = screen.getByText('Next');
      await user.click(nextButton);
      expect(mockHandlers.onNext).toHaveBeenCalled();
    });

    it('should call previous on prev button click', async () => {
      const user = userEvent.setup();
      render(
        <PlayerBarV2
          player={mockPlayer}
          {...mockHandlers}
        />
      );
      const prevButton = screen.getByText('Prev');
      await user.click(prevButton);
      expect(mockHandlers.onPrevious).toHaveBeenCalled();
    });
  });

  describe('Volume Control', () => {
    it('should display current volume', () => {
      render(
        <PlayerBarV2
          player={{ ...mockPlayer, volume: 75 }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('75')).toBeInTheDocument();
    });

    it('should update volume on slider change', async () => {
      render(
        <PlayerBarV2
          player={mockPlayer}
          {...mockHandlers}
        />
      );
      const volumeSlider = screen.getByTestId('volume-slider') as HTMLInputElement;
      fireEvent.change(volumeSlider, { target: { value: '50' } });
      await waitFor(() => {
        expect(mockHandlers.onVolumeChange).toHaveBeenCalledWith(50);
      });
    });
  });

  describe('Progress Bar', () => {
    it('should display current time', () => {
      render(
        <PlayerBarV2
          player={{ ...mockPlayer, currentTime: 90 }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('1:30')).toBeInTheDocument();
    });

    it('should display total duration', () => {
      render(
        <PlayerBarV2
          player={mockPlayer}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('3:00')).toBeInTheDocument();
    });

    it('should seek on progress bar change', async () => {
      render(
        <PlayerBarV2
          player={mockPlayer}
          {...mockHandlers}
        />
      );
      const progressSlider = screen.getByTestId('progress-slider') as HTMLInputElement;
      fireEvent.change(progressSlider, { target: { value: '90' } });
      await waitFor(() => {
        expect(mockHandlers.onSeek).toHaveBeenCalledWith(90);
      });
    });
  });

  describe('Enhancement Toggle', () => {
    it('should show enhancement toggle button', () => {
      render(
        <PlayerBarV2
          player={mockPlayer}
          {...mockHandlers}
        />
      );
      const toggleButton = screen.getByTestId('enhancement-toggle');
      expect(toggleButton).toBeInTheDocument();
    });

    it('should show enabled state when enhancement is on', () => {
      render(
        <PlayerBarV2
          player={{ ...mockPlayer, isEnhanced: true }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('Enhancement On')).toBeInTheDocument();
    });

    it('should show disabled state when enhancement is off', () => {
      render(
        <PlayerBarV2
          player={{ ...mockPlayer, isEnhanced: false }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('Enhancement Off')).toBeInTheDocument();
    });

    it('should call toggle handler on click', async () => {
      const user = userEvent.setup();
      render(
        <PlayerBarV2
          player={mockPlayer}
          {...mockHandlers}
        />
      );
      const toggleButton = screen.getByTestId('enhancement-toggle');
      await user.click(toggleButton);
      expect(mockHandlers.onEnhancementToggle).toHaveBeenCalled();
    });
  });

  describe('Empty State', () => {
    it('should handle no current track', () => {
      render(
        <PlayerBarV2
          player={{ ...mockPlayer, currentTrack: null }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('No Track')).toBeInTheDocument();
    });
  });

  describe('State Synchronization', () => {
    it('should update when player state changes', () => {
      const { rerender } = render(
        <PlayerBarV2
          player={mockPlayer}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('Test Track')).toBeInTheDocument();

      rerender(
        <PlayerBarV2
          player={{
            ...mockPlayer,
            currentTrack: { id: 2, title: 'New Track', artist: 'New Artist', duration: 240 },
          }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('New Track')).toBeInTheDocument();
      expect(screen.getByText('New Artist')).toBeInTheDocument();
    });

    it('should update when enhancement state changes', async () => {
      const { rerender } = render(
        <PlayerBarV2
          player={{ ...mockPlayer, isEnhanced: false }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('Enhancement Off')).toBeInTheDocument();

      rerender(
        <PlayerBarV2
          player={{ ...mockPlayer, isEnhanced: true }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('Enhancement On')).toBeInTheDocument();
    });

    it('should update when volume changes', () => {
      const { rerender } = render(
        <PlayerBarV2
          player={{ ...mockPlayer, volume: 100 }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('100')).toBeInTheDocument();

      rerender(
        <PlayerBarV2
          player={{ ...mockPlayer, volume: 50 }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('50')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero duration tracks', () => {
      render(
        <PlayerBarV2
          player={{ ...mockPlayer, duration: 0 }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should handle very long track titles', () => {
      const longTitle = 'A'.repeat(100);
      render(
        <PlayerBarV2
          player={{
            ...mockPlayer,
            currentTrack: { ...mockPlayer.currentTrack, title: longTitle },
          }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText(longTitle, { exact: true })).toBeInTheDocument();
    });

    it('should handle minimum volume', () => {
      render(
        <PlayerBarV2
          player={{ ...mockPlayer, volume: 0 }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('0')).toBeInTheDocument();
    });

    it('should handle maximum volume', () => {
      render(
        <PlayerBarV2
          player={{ ...mockPlayer, volume: 200 }}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('200')).toBeInTheDocument();
    });
  });
});
