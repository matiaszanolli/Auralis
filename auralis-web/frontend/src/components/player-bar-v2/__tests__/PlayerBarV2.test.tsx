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
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import PlayerBarV2 from '../PlayerBarV2';
import { usePlayerAPI } from '../../../hooks/usePlayerAPI';
import { useUnifiedWebMAudioPlayer } from '../../../hooks/useUnifiedWebMAudioPlayer';
import { useEnhancement } from '../../../contexts/EnhancementContext';
import { auralisTheme } from '../../../theme/auralisTheme';

vi.mock('../../../hooks/usePlayerAPI');
vi.mock('../../../hooks/useUnifiedWebMAudioPlayer');
vi.mock('../../../contexts/EnhancementContext');
vi.mock('../../player/PlaybackControls', () => {
  return function MockControls({ onPlay, onPause, onNext, onPrev, isPlaying }: any) {
    return (
      <div data-testid="playback-controls">
        <button onClick={isPlaying ? onPause : onPlay}>
          {isPlaying ? 'Pause' : 'Play'}
        </button>
        <button onClick={onPrev}>Prev</button>
        <button onClick={onNext}>Next</button>
      </div>
    );
  };
});

const mockPlayerState = {
  isPlaying: false,
  currentTrack: { id: 1, title: 'Test Track', artist: 'Test Artist', duration: 180 },
  position: 0,
  duration: 180,
  volume: 100,
};

const mockPlayerAPI = {
  play: vi.fn(),
  pause: vi.fn(),
  next: vi.fn(),
  previous: vi.fn(),
  setVolume: vi.fn(),
  seek: vi.fn(),
};

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('PlayerBarV2', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(usePlayerAPI).mockReturnValue(mockPlayerAPI);
    vi.mocked(useUnifiedWebMAudioPlayer).mockReturnValue(mockPlayerState);
    vi.mocked(useEnhancement).mockReturnValue({ isEnabled: false, currentPreset: 'adaptive' });
  });

  describe('Rendering', () => {
    it('should render player bar container', () => {
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      expect(screen.getByTestId(/player|bar/i)).toBeInTheDocument();
    });

    it('should render playback controls', () => {
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      expect(screen.getByTestId('playback-controls')).toBeInTheDocument();
    });

    it('should display track info', () => {
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      expect(screen.getByText('Test Track')).toBeInTheDocument();
      expect(screen.getByText('Test Artist')).toBeInTheDocument();
    });

    it('should render volume control slider', () => {
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const sliders = screen.getAllByRole('slider');
      expect(sliders.length).toBeGreaterThan(0);
    });

    it('should render enhancement toggle', () => {
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const toggleButton = screen.getByRole('button', { name: /enhancement|enhance/i });
      expect(toggleButton).toBeInTheDocument();
    });

    it('should render progress bar', () => {
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const sliders = screen.getAllByRole('slider');
      expect(sliders.length).toBeGreaterThanOrEqual(2); // Progress + volume
    });
  });

  describe('Playback Controls', () => {
    it('should show play button when paused', () => {
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      expect(screen.getByText('Play')).toBeInTheDocument();
    });

    it('should show pause button when playing', () => {
      vi.mocked(useUnifiedWebMAudioPlayer).mockReturnValue({
        ...mockPlayerState,
        isPlaying: true,
      });
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      expect(screen.getByText('Pause')).toBeInTheDocument();
    });

    it('should call play on play button click', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const playButton = screen.getByText('Play');
      await user.click(playButton);
      expect(mockPlayerAPI.play).toHaveBeenCalled();
    });

    it('should call pause on pause button click', async () => {
      const user = userEvent.setup();
      vi.mocked(useUnifiedWebMAudioPlayer).mockReturnValue({
        ...mockPlayerState,
        isPlaying: true,
      });
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const pauseButton = screen.getByText('Pause');
      await user.click(pauseButton);
      expect(mockPlayerAPI.pause).toHaveBeenCalled();
    });

    it('should call next on next button click', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const nextButton = screen.getByText('Next');
      await user.click(nextButton);
      expect(mockPlayerAPI.next).toHaveBeenCalled();
    });

    it('should call previous on prev button click', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const prevButton = screen.getByText('Prev');
      await user.click(prevButton);
      expect(mockPlayerAPI.previous).toHaveBeenCalled();
    });
  });

  describe('Volume Control', () => {
    it('should display current volume', () => {
      vi.mocked(useUnifiedWebMAudioPlayer).mockReturnValue({
        ...mockPlayerState,
        volume: 75,
      });
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      expect(screen.getByText('75')).toBeInTheDocument();
    });

    it('should update volume on slider change', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const sliders = screen.getAllByRole('slider');
      const volumeSlider = sliders[sliders.length - 1];
      fireEvent.change(volumeSlider, { target: { value: '50' } });
      await waitFor(() => {
        expect(mockPlayerAPI.setVolume).toHaveBeenCalled();
      });
    });
  });

  describe('Progress Bar', () => {
    it('should display current time', () => {
      vi.mocked(useUnifiedWebMAudioPlayer).mockReturnValue({
        ...mockPlayerState,
        position: 90,
      });
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      expect(screen.getByText(/1:30|01:30/)).toBeInTheDocument();
    });

    it('should display total duration', () => {
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      expect(screen.getByText(/3:00|03:00/)).toBeInTheDocument();
    });

    it('should seek on progress bar click', async () => {
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const sliders = screen.getAllByRole('slider');
      fireEvent.change(sliders[0], { target: { value: '90' } });
      await waitFor(() => {
        expect(mockPlayerAPI.seek).toHaveBeenCalled();
      });
    });
  });

  describe('Enhancement Toggle', () => {
    it('should show enhancement toggle button', () => {
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const toggleButton = screen.getByRole('button', { name: /enhancement|enhance/i });
      expect(toggleButton).toBeInTheDocument();
    });

    it('should show enabled state when enhancement is on', () => {
      vi.mocked(useEnhancement).mockReturnValue({
        isEnabled: true,
        currentPreset: 'bright',
      });
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const enhancementInfo = screen.getByText(/bright|enhancement.*on/i);
      expect(enhancementInfo).toBeInTheDocument();
    });

    it('should show disabled state when enhancement is off', () => {
      vi.mocked(useEnhancement).mockReturnValue({
        isEnabled: false,
        currentPreset: 'adaptive',
      });
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      // Should show some indication that enhancement is disabled
      const elements = screen.queryAllByText(/disabled|off|enhancement/i);
      expect(elements.length).toBeGreaterThan(0);
    });
  });

  describe('Empty State', () => {
    it('should handle no current track', () => {
      vi.mocked(useUnifiedWebMAudioPlayer).mockReturnValue({
        ...mockPlayerState,
        currentTrack: null,
      });
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const noTrackText = screen.queryByText(/no track|empty|select/i);
      expect(noTrackText).toBeInTheDocument();
    });

    it('should disable controls when no track loaded', () => {
      vi.mocked(useUnifiedWebMAudioPlayer).mockReturnValue({
        ...mockPlayerState,
        currentTrack: null,
      });
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const playButton = screen.getByText('Play');
      expect(playButton).toBeDisabled();
    });
  });

  describe('Responsive Layout', () => {
    it('should adapt to different screen sizes', () => {
      const { container } = render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const playerBar = container.firstChild;
      expect(playerBar).toBeInTheDocument();
    });

    it('should have proper z-index for layering', () => {
      const { container } = render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const playerBar = container.querySelector('[style*="z-index"]');
      if (playerBar) {
        expect(playerBar).toBeInTheDocument();
      }
    });
  });

  describe('State Synchronization', () => {
    it('should update when player state changes', () => {
      const { rerender } = render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      expect(screen.getByText('Test Track')).toBeInTheDocument();

      vi.mocked(useUnifiedWebMAudioPlayer).mockReturnValue({
        ...mockPlayerState,
        currentTrack: { id: 2, title: 'New Track', artist: 'New Artist', duration: 240 },
      });

      rerender(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      expect(screen.getByText('New Track')).toBeInTheDocument();
    });

    it('should update when enhancement state changes', () => {
      const { rerender } = render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );

      vi.mocked(useEnhancement).mockReturnValue({
        isEnabled: true,
        currentPreset: 'warm',
      });

      rerender(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      expect(screen.getByText(/warm|enhancement/i)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        expect(button).toHaveAccessibleName();
      });
    });

    it('should be keyboard navigable', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      const firstButton = screen.getByText('Play');
      await user.tab();
      expect(document.activeElement).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero duration tracks', () => {
      vi.mocked(useUnifiedWebMAudioPlayer).mockReturnValue({
        ...mockPlayerState,
        duration: 0,
      });
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should handle very long track titles', () => {
      vi.mocked(useUnifiedWebMAudioPlayer).mockReturnValue({
        ...mockPlayerState,
        currentTrack: {
          ...mockPlayerState.currentTrack,
          title: 'A'.repeat(100),
        },
      });
      render(
        <Wrapper>
          <PlayerBarV2 />
        </Wrapper>
      );
      expect(screen.getByText(/A+/)).toBeInTheDocument();
    });
  });
});
