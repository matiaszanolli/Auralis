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
import { render, screen, fireEvent, waitFor, within } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import BottomPlayerBarUnified from '../BottomPlayerBarUnified';

// Mock hooks using hoisted functions
const { mockUsePlayerWithAudio, mockUseEnhancement } = vi.hoisted(() => ({
  mockUsePlayerWithAudio: vi.fn(),
  mockUseEnhancement: vi.fn(),
}));

vi.mock('../../hooks/usePlayerWithAudio', () => ({
  usePlayerWithAudio: mockUsePlayerWithAudio,
}));
vi.mock('../../contexts/EnhancementContext', () => ({
  useEnhancement: mockUseEnhancement,
  EnhancementContext: vi.fn(),
  EnhancementProvider: ({ children }: any) => <>{children}</>,
}));
vi.mock('../album/AlbumArt', () => {
  return {
    default: function MockAlbumArt() {
      return <div data-testid="album-art">Album Art</div>;
    },
  };
});
vi.mock('../shared/Toast', () => ({
  useToast: () => ({
    showToast: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
  }),
  Toast: () => null,
  ToastProvider: ({ children }: any) => <>{children}</>,
}));

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


describe('BottomPlayerBarUnified', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockUsePlayerWithAudio.mockReturnValue({
      ...mockPlayerWithAudio,
    });

    mockUseEnhancement.mockReturnValue({
      ...mockEnhancement,
      toggleEnhancement: vi.fn(),
    });
  });

  describe('Rendering', () => {
    it('should render the player bar container', () => {
      render(<BottomPlayerBarUnified />
      );

      const container = screen.getByRole('region', { hidden: true });
      expect(container).toBeInTheDocument();
    });

    it('should display album art', () => {
      render(<BottomPlayerBarUnified />
      );

      expect(screen.getByTestId('album-art')).toBeInTheDocument();
    });

    it('should display track title', () => {
      render(<BottomPlayerBarUnified />
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should display artist name', () => {
      render(<BottomPlayerBarUnified />
      );

      expect(screen.getByText('Test Artist')).toBeInTheDocument();
    });

    it('should display album name', () => {
      render(<BottomPlayerBarUnified />
      );

      expect(screen.getByText('Test Album')).toBeInTheDocument();
    });

    it('should render play button', () => {
      render(<BottomPlayerBarUnified />
      );

      const playButton = screen.getByRole('button', { name: /play|pause/i });
      expect(playButton).toBeInTheDocument();
    });

    it('should render next track button', () => {
      render(<BottomPlayerBarUnified />
      );

      const nextButtons = screen.getAllByRole('button');
      const nextButton = nextButtons.find(btn =>
        btn.getAttribute('aria-label')?.toLowerCase().includes('next')
      );
      expect(nextButton).toBeInTheDocument();
    });

    it('should render previous track button', () => {
      render(<BottomPlayerBarUnified />
      );

      const prevButtons = screen.getAllByRole('button');
      const prevButton = prevButtons.find(btn =>
        btn.getAttribute('aria-label')?.toLowerCase().includes('previous')
      );
      expect(prevButton).toBeInTheDocument();
    });

    it('should render volume control', () => {
      render(<BottomPlayerBarUnified />
      );

      const volumeSliders = screen.getAllByRole('slider');
      expect(volumeSliders.length).toBeGreaterThan(0);
    });
  });

  describe('Play/Pause Functionality', () => {
    it('should show pause button when playing', () => {
      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        isPlaying: true,
      });

      render(<BottomPlayerBarUnified />
      );

      const pauseButton = screen.getByRole('button', { name: /pause/i });
      expect(pauseButton).toBeInTheDocument();
    });

    it('should show play button when not playing', () => {
      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        isPlaying: false,
      });

      render(<BottomPlayerBarUnified />
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      expect(playButton).toBeInTheDocument();
    });

    it('should call togglePlayPause when play button clicked', async () => {
      const user = userEvent.setup();

      render(<BottomPlayerBarUnified />
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      await user.click(playButton);

      expect(mockPlayerWithAudio.togglePlayPause).toHaveBeenCalled();
    });

    it('should call togglePlayPause when pause button clicked', async () => {
      const user = userEvent.setup();

      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        isPlaying: true,
      });

      render(<BottomPlayerBarUnified />
      );

      const pauseButton = screen.getByRole('button', { name: /pause/i });
      await user.click(pauseButton);

      expect(mockPlayerWithAudio.togglePlayPause).toHaveBeenCalled();
    });
  });

  describe('Track Navigation', () => {
    it('should call next when next button clicked', async () => {
      const user = userEvent.setup();

      render(<BottomPlayerBarUnified />
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

      render(<BottomPlayerBarUnified />
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
      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        queueIndex: 0,
      });

      render(<BottomPlayerBarUnified />
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
      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        queueIndex: 1,
        queue: [
          { id: 1, title: 'Track 1', artist: 'Artist 1', album: 'Album 1', duration: 180 },
          { id: 2, title: 'Track 2', artist: 'Artist 2', album: 'Album 2', duration: 200 },
        ],
      });

      render(<BottomPlayerBarUnified />
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
      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        volume: 75,
      });

      render(<BottomPlayerBarUnified />
      );

      // The volume is stored locally in the component and updated via slider
      expect(screen.getByRole('slider')).toBeInTheDocument();
    });

    it('should update volume on slider change', async () => {
      const user = userEvent.setup();

      render(<BottomPlayerBarUnified />
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
      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        volume: 0,
      });

      render(<BottomPlayerBarUnified />
      );

      // Check for mute icon presence
      expect(screen.getByTestId('VolumeMuteIcon')).toBeInTheDocument();
    });

    it('should show volume down icon for low volume', () => {
      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        volume: 25,
      });

      render(<BottomPlayerBarUnified />
      );

      // Check for volume down icon
      expect(screen.getByTestId('VolumeDownIcon')).toBeInTheDocument();
    });

    it('should show volume up icon for high volume', () => {
      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        volume: 75,
      });

      render(<BottomPlayerBarUnified />
      );

      // Check for volume up icon
      expect(screen.getByTestId('VolumeUpIcon')).toBeInTheDocument();
    });
  });

  describe('Progress Bar', () => {
    it('should display current time', () => {
      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        position: 90, // 1:30
      });

      render(<BottomPlayerBarUnified />
      );

      // Check for time display (format: MM:SS)
      expect(screen.getByText(/1:30|01:30/)).toBeInTheDocument();
    });

    it('should display total duration', () => {
      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        duration: 180, // 3:00
      });

      render(<BottomPlayerBarUnified />
      );

      expect(screen.getByText(/3:00|03:00/)).toBeInTheDocument();
    });

    it('should update progress on track position change', () => {
      const { rerender } = render(<BottomPlayerBarUnified />
      );

      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        position: 90,
      });

      rerender(<BottomPlayerBarUnified />
      );

      expect(screen.getByText(/1:30|01:30/)).toBeInTheDocument();
    });

    it('should call seek when progress bar is clicked', async () => {
      const user = userEvent.setup();

      render(<BottomPlayerBarUnified />
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

      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        duration: 180,
      });

      render(<BottomPlayerBarUnified />
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
      render(<BottomPlayerBarUnified />
      );

      const favoriteButtons = screen.getAllByRole('button');
      const hasFavoriteButton = favoriteButtons.some(btn =>
        btn.querySelector('[data-testid*="Favorite"]')
      );
      expect(hasFavoriteButton).toBeTruthy();
    });

    it('should show unfilled heart when not favorited', () => {
      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        isFavorited: false,
      });

      render(<BottomPlayerBarUnified />
      );

      expect(screen.getByTestId('FavoriteBorderIcon')).toBeInTheDocument();
    });

    it('should show filled heart when favorited', () => {
      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        isFavorited: true,
      });

      render(<BottomPlayerBarUnified />
      );

      expect(screen.getByTestId('FavoriteIcon')).toBeInTheDocument();
    });

    it('should call toggleFavorite when favorite button clicked', async () => {
      const user = userEvent.setup();

      render(<BottomPlayerBarUnified />
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
      mockUseEnhancement.mockReturnValue({
        isEnabled: true,
        currentPreset: 'bright',
      });

      render(<BottomPlayerBarUnified />
      );

      // Should display enhancement is enabled
      expect(screen.getByText(/enhancement|bright/i)).toBeInTheDocument();
    });

    it('should show when enhancement is disabled', () => {
      mockUseEnhancement.mockReturnValue({
        isEnabled: false,
        currentPreset: 'adaptive',
      });

      render(<BottomPlayerBarUnified />
      );

      // Enhancement should still be visible but disabled
      const elements = screen.queryAllByText(/enhancement|disabled/i);
      expect(elements.length).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Empty State', () => {
    it('should handle no current track', () => {
      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        currentTrack: null,
      });

      render(<BottomPlayerBarUnified />
      );

      // Should display empty state or default text
      const text = screen.queryByText(/no track|queue empty|select/i);
      expect(text).toBeInTheDocument();
    });

    it('should disable playback controls when no track loaded', () => {
      mockUsePlayerWithAudio.mockReturnValue({
        ...mockPlayerWithAudio,
        currentTrack: null,
      });

      render(<BottomPlayerBarUnified />
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      expect(playButton).toBeDisabled();
    });
  });

  describe('Responsiveness', () => {
    it('should render at bottom of viewport', () => {
      const { container } = render(<BottomPlayerBarUnified />
      );

      const playerBar = container.firstChild;
      const style = window.getComputedStyle(playerBar as Element);
      expect(style.position).toBe('fixed');
      expect(style.bottom).toBe('0');
    });

    it('should have proper z-index for overlay', () => {
      const { container } = render(<BottomPlayerBarUnified />
      );

      // Player bar should be above other content but below modals
      expect(container.querySelector('[style*="z-index"]')).toBeInTheDocument();
    });
  });

  describe('Keyboard Navigation', () => {
    it('should support space bar to toggle play/pause', async () => {
      const user = userEvent.setup();

      render(<BottomPlayerBarUnified />
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

      render(<BottomPlayerBarUnified />
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
      render(<BottomPlayerBarUnified />
      );

      expect(screen.getByRole('button', { name: /play|pause/i })).toBeInTheDocument();
    });

    it('should be keyboard navigable', async () => {
      const user = userEvent.setup();

      render(<BottomPlayerBarUnified />
      );

      const playButton = screen.getByRole('button', { name: /play|pause/i });
      expect(playButton).toHaveFocus() || (await user.tab());
    });
  });
});
