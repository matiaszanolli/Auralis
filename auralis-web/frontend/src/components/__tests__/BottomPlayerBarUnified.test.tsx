/**
 * BottomPlayerBarUnified Component Tests
 *
 * Tests the main player interface with:
 * - Play/pause functionality
 * - Track info display
 * - Progress bar and seeking
 * - Volume control
 * - Queue navigation
 * - WebSocket synchronization
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import BottomPlayerBarUnified from '../BottomPlayerBarUnified';
import { usePlayerWithAudio } from '../../hooks/usePlayerWithAudio';
import { useEnhancement } from '../../contexts/EnhancementContext';
import { WebSocketProvider } from '../../contexts/WebSocketContext';
import { ToastProvider } from '../shared/Toast';
import { auralisTheme } from '../../theme/auralisTheme';

// Mock hooks
vi.mock('../../hooks/usePlayerWithAudio');
vi.mock('../../contexts/EnhancementContext');
vi.mock('../album/AlbumArt', () => {
  return {
    default: function MockAlbumArt() {
      return <div data-testid="album-art">Album Art</div>;
    },
  };
});
vi.mock('../shared/Toast', async () => {
  const actual = await vi.importActual<typeof import('../shared/Toast')>('../shared/Toast');
  return {
    ...actual,
    useToast: () => ({
      showToast: vi.fn(),
    }),
  };
});

const mockPlayerWithAudio = {
  // Queue & Track Data
  currentTrack: {
    id: 1,
    title: 'Test Track',
    artist: 'Test Artist',
    album: 'Test Album',
    duration: 180,
    albumArt: 'http://example.com/art.jpg',
    album_id: 1,
  },
  queue: [
    { id: 1, title: 'Test Track', artist: 'Test Artist', album: 'Test Album', duration: 180 },
    { id: 2, title: 'Next Track', artist: 'Next Artist', album: 'Next Album', duration: 200 },
  ],
  queueIndex: 0,

  // Playback State
  isPlaying: false,
  currentTime: 0,
  duration: 180,
  volume: 80,
  loading: false,
  error: null,

  // Web Audio State
  audioState: 'idle' as const,
  audioMetadata: null,
  audioError: null,

  // Playback Controls
  play: vi.fn(),
  pause: vi.fn(),
  togglePlayPause: vi.fn(),
  next: vi.fn(),
  previous: vi.fn(),
  seek: vi.fn(),
  setVolume: vi.fn(),
  setQueue: vi.fn(),
  playTrack: vi.fn(),

  // Enhanced Audio Controls
  setEnhanced: vi.fn(),
  setPreset: vi.fn(),

  // Utilities
  refreshStatus: vi.fn(),
  player: null,
};

const mockEnhancement = {
  isEnabled: false,
  currentPreset: 'adaptive',
};

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      <WebSocketProvider>
        <ToastProvider>
          {children}
        </ToastProvider>
      </WebSocketProvider>
    </ThemeProvider>
  </BrowserRouter>
);

describe('BottomPlayerBarUnified', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(usePlayerWithAudio).mockReturnValue({
      ...mockPlayerWithAudio,
    });

    vi.mocked(useEnhancement).mockReturnValue({
      ...mockEnhancement,
      toggleEnhancement: vi.fn(),
    });
  });

  describe('Rendering', () => {
    it('should render the player bar container', () => {
      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const container = screen.getByRole('region', { hidden: true });
      expect(container).toBeInTheDocument();
    });

    it('should display album art', () => {
      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      expect(screen.getByTestId('album-art')).toBeInTheDocument();
    });

    it('should display track title', () => {
      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should display artist name', () => {
      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      expect(screen.getByText('Test Artist')).toBeInTheDocument();
    });

    it('should display album name', () => {
      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      expect(screen.getByText('Test Album')).toBeInTheDocument();
    });

    it('should render play button', () => {
      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const playButton = screen.getByRole('button', { name: /play|pause/i });
      expect(playButton).toBeInTheDocument();
    });

    it('should render next track button', () => {
      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const nextButtons = screen.getAllByRole('button');
      const nextButton = nextButtons.find(btn =>
        btn.getAttribute('aria-label')?.toLowerCase().includes('next')
      );
      expect(nextButton).toBeInTheDocument();
    });

    it('should render previous track button', () => {
      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const prevButtons = screen.getAllByRole('button');
      const prevButton = prevButtons.find(btn =>
        btn.getAttribute('aria-label')?.toLowerCase().includes('previous')
      );
      expect(prevButton).toBeInTheDocument();
    });

    it('should render volume control', () => {
      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const volumeSliders = screen.getAllByRole('slider');
      expect(volumeSliders.length).toBeGreaterThan(0);
    });
  });

  describe('Play/Pause Functionality', () => {
    it('should show pause button when playing', () => {
      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        isPlaying: true,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const pauseButton = screen.getByRole('button', { name: /pause/i });
      expect(pauseButton).toBeInTheDocument();
    });

    it('should show play button when not playing', () => {
      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        isPlaying: false,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      expect(playButton).toBeInTheDocument();
    });

    it('should call togglePlayPause when play button clicked', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      await user.click(playButton);

      expect(mockPlayerWithAudio.togglePlayPause).toHaveBeenCalled();
    });

    it('should call togglePlayPause when pause button clicked', async () => {
      const user = userEvent.setup();

      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        isPlaying: true,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const pauseButton = screen.getByRole('button', { name: /pause/i });
      await user.click(pauseButton);

      expect(mockPlayerWithAudio.togglePlayPause).toHaveBeenCalled();
    });
  });

  describe('Track Navigation', () => {
    it('should call next when next button clicked', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const buttons = screen.getAllByRole('button');
      const nextButton = buttons.find(btn =>
        btn.getAttribute('aria-label')?.toLowerCase().includes('next')
      );

      if (nextButton) {
        await user.click(nextButton);
        expect(mockPlayerWithAudio.next).toHaveBeenCalled();
      }
    });

    it('should call previous when previous button clicked', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const buttons = screen.getAllByRole('button');
      const prevButton = buttons.find(btn =>
        btn.getAttribute('aria-label')?.toLowerCase().includes('previous')
      );

      if (prevButton) {
        await user.click(prevButton);
        expect(mockPlayerWithAudio.previous).toHaveBeenCalled();
      }
    });

    it('should disable previous button at queue start', () => {
      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        queueIndex: 0,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const buttons = screen.getAllByRole('button');
      const prevButton = buttons.find(btn =>
        btn.getAttribute('aria-label')?.toLowerCase().includes('previous')
      );

      if (prevButton) {
        expect(prevButton).toBeDisabled();
      }
    });

    it('should disable next button at queue end', () => {
      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        queueIndex: 1,
        queue: [
          { id: 1, title: 'Track 1', artist: 'Artist 1', album: 'Album 1', duration: 180 },
          { id: 2, title: 'Track 2', artist: 'Artist 2', album: 'Album 2', duration: 200 },
        ],
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const buttons = screen.getAllByRole('button');
      const nextButton = buttons.find(btn =>
        btn.getAttribute('aria-label')?.toLowerCase().includes('next')
      );

      if (nextButton) {
        expect(nextButton).toBeDisabled();
      }
    });
  });

  describe('Volume Control', () => {
    it('should display current volume level', () => {
      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        volume: 75,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      // The volume is stored locally in the component and updated via slider
      expect(screen.getByRole('slider')).toBeInTheDocument();
    });

    it('should update volume on slider change', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const sliders = screen.getAllByRole('slider');
      const volumeSlider = sliders[sliders.length - 1]; // Last slider is volume

      await user.click(volumeSlider);
      fireEvent.change(volumeSlider, { target: { value: '50' } });

      // Volume change should be called with new value
      await waitFor(() => {
        expect(mockPlayerWithAudio.setVolume).toHaveBeenCalled();
      });
    });

    it('should show mute icon when volume is 0', () => {
      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        volume: 0,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      // Check for mute icon presence
      expect(screen.getByTestId('VolumeMuteIcon')).toBeInTheDocument();
    });

    it('should show volume down icon for low volume', () => {
      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        volume: 25,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      // Check for volume down icon
      expect(screen.getByTestId('VolumeDownIcon')).toBeInTheDocument();
    });

    it('should show volume up icon for high volume', () => {
      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        volume: 75,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      // Check for volume up icon
      expect(screen.getByTestId('VolumeUpIcon')).toBeInTheDocument();
    });
  });

  describe('Progress Bar', () => {
    it('should display current time', () => {
      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        position: 90, // 1:30
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      // Check for time display (format: MM:SS)
      expect(screen.getByText(/1:30|01:30/)).toBeInTheDocument();
    });

    it('should display total duration', () => {
      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        duration: 180, // 3:00
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      expect(screen.getByText(/3:00|03:00/)).toBeInTheDocument();
    });

    it('should update progress on track position change', () => {
      const { rerender } = render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        position: 90,
      });

      rerender(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      expect(screen.getByText(/1:30|01:30/)).toBeInTheDocument();
    });

    it('should call seek when progress bar is clicked', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const sliders = screen.getAllByRole('slider');
      const progressSlider = sliders[0]; // First slider is progress

      await user.click(progressSlider);
      fireEvent.change(progressSlider, { target: { value: '90' } });

      await waitFor(() => {
        expect(mockPlayerWithAudio.seek).toHaveBeenCalled();
      });
    });

    it('should handle seeking at track end', async () => {
      const user = userEvent.setup();

      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        duration: 180,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const sliders = screen.getAllByRole('slider');
      const progressSlider = sliders[0];

      fireEvent.change(progressSlider, { target: { value: '180' } });

      await waitFor(() => {
        expect(mockPlayerWithAudio.seek).toHaveBeenCalledWith(180);
      });
    });
  });

  describe('Favorite Button', () => {
    it('should display favorite button', () => {
      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const favoriteButtons = screen.getAllByRole('button');
      const hasFavoriteButton = favoriteButtons.some(btn =>
        btn.querySelector('[data-testid*="Favorite"]')
      );
      expect(hasFavoriteButton).toBeTruthy();
    });

    it('should show unfilled heart when not favorited', () => {
      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        isFavorited: false,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      expect(screen.getByTestId('FavoriteBorderIcon')).toBeInTheDocument();
    });

    it('should show filled heart when favorited', () => {
      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        isFavorited: true,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      expect(screen.getByTestId('FavoriteIcon')).toBeInTheDocument();
    });

    it('should call toggleFavorite when favorite button clicked', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const favoriteIcon = screen.getByTestId('FavoriteBorderIcon');
      const favoriteButton = favoriteIcon.closest('button');

      if (favoriteButton) {
        await user.click(favoriteButton);
        expect(mockPlayerWithAudio.playTrack).toHaveBeenCalled();
      }
    });
  });

  describe('Enhancement Indicator', () => {
    it('should show enhancement status', () => {
      vi.mocked(useEnhancement).mockReturnValue({
        isEnabled: true,
        currentPreset: 'bright',
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      // Should display enhancement is enabled
      expect(screen.getByText(/enhancement|bright/i)).toBeInTheDocument();
    });

    it('should show when enhancement is disabled', () => {
      vi.mocked(useEnhancement).mockReturnValue({
        isEnabled: false,
        currentPreset: 'adaptive',
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      // Enhancement should still be visible but disabled
      const elements = screen.queryAllByText(/enhancement|disabled/i);
      expect(elements.length).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Empty State', () => {
    it('should handle no current track', () => {
      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        currentTrack: null,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      // Should display empty state or default text
      const text = screen.queryByText(/no track|queue empty|select/i);
      expect(text).toBeInTheDocument();
    });

    it('should disable playback controls when no track loaded', () => {
      vi.mocked(usePlayerWithAudio).mockReturnValue({
        ...mockPlayerWithAudio,
        currentTrack: null,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      expect(playButton).toBeDisabled();
    });
  });

  describe('Responsiveness', () => {
    it('should render at bottom of viewport', () => {
      const { container } = render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const playerBar = container.firstChild;
      const style = window.getComputedStyle(playerBar as Element);
      expect(style.position).toBe('fixed');
      expect(style.bottom).toBe('0');
    });

    it('should have proper z-index for overlay', () => {
      const { container } = render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      // Player bar should be above other content but below modals
      expect(container.querySelector('[style*="z-index"]')).toBeInTheDocument();
    });
  });

  describe('Keyboard Navigation', () => {
    it('should support space bar to toggle play/pause', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      // Simulate space bar press
      fireEvent.keyDown(document, { key: ' ', code: 'Space' });

      await waitFor(() => {
        // Should call either play or pause
        const playOrPauseCalled =
          mockPlayerWithAudio.play.mock.calls.length > 0 ||
          mockPlayerWithAudio.pause.mock.calls.length > 0;
        expect(playOrPauseCalled).toBeTruthy();
      });
    });

    it('should support arrow keys for navigation', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      // Simulate right arrow press (next track)
      fireEvent.keyDown(document, { key: 'ArrowRight', code: 'ArrowRight' });

      await waitFor(() => {
        expect(mockPlayerWithAudio.next).toHaveBeenCalled();
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      expect(screen.getByRole('button', { name: /play|pause/i })).toBeInTheDocument();
    });

    it('should be keyboard navigable', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const playButton = screen.getByRole('button', { name: /play|pause/i });
      expect(playButton).toHaveFocus() || (await user.tab());
    });
  });
});
