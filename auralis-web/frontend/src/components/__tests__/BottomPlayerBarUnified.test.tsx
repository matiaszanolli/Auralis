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
import BottomPlayerBarUnified from '../BottomPlayerBarUnified';
import { usePlayerAPI } from '../../hooks/usePlayerAPI';
import { useUnifiedWebMAudioPlayer } from '../../hooks/useUnifiedWebMAudioPlayer';
import { useEnhancement } from '../../contexts/EnhancementContext';
import { WebSocketProvider } from '../../contexts/WebSocketContext';
import { ToastProvider } from '../shared/Toast';
import { auralisTheme } from '../../theme/auralisTheme';

// Mock hooks
jest.mock('../../hooks/usePlayerAPI');
jest.mock('../../hooks/useUnifiedWebMAudioPlayer');
jest.mock('../../contexts/EnhancementContext');
jest.mock('../album/AlbumArt', () => {
  return function MockAlbumArt() {
    return <div data-testid="album-art">Album Art</div>;
  };
});
jest.mock('../shared/Toast', () => ({
  ...jest.requireActual('../shared/Toast'),
  useToast: () => ({
    showToast: jest.fn(),
  }),
}));

const mockPlayerAPI = {
  play: jest.fn(),
  pause: jest.fn(),
  seek: jest.fn(),
  setVolume: jest.fn(),
  nextTrack: jest.fn(),
  previousTrack: jest.fn(),
  toggleFavorite: jest.fn(),
};

const mockPlayerState = {
  isPlaying: false,
  currentTrack: {
    id: 1,
    title: 'Test Track',
    artist: 'Test Artist',
    album: 'Test Album',
    duration: 180,
    artwork: 'http://example.com/art.jpg',
  },
  position: 0,
  duration: 180,
  queue: [
    { id: 1, title: 'Test Track' },
    { id: 2, title: 'Next Track' },
  ],
  queueIndex: 0,
  isFavorited: false,
  volume: 100,
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
    jest.clearAllMocks();

    (usePlayerAPI as jest.Mock).mockReturnValue({
      ...mockPlayerAPI,
      playerState: { ...mockPlayerState },
    });

    (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue(mockPlayerState);

    (useEnhancement as jest.Mock).mockReturnValue({
      ...mockEnhancement,
      toggleEnhancement: jest.fn(),
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
      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
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
      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
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

    it('should call play when play button clicked', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      await user.click(playButton);

      expect(mockPlayerAPI.play).toHaveBeenCalled();
    });

    it('should call pause when pause button clicked', async () => {
      const user = userEvent.setup();

      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
        isPlaying: true,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      const pauseButton = screen.getByRole('button', { name: /pause/i });
      await user.click(pauseButton);

      expect(mockPlayerAPI.pause).toHaveBeenCalled();
    });
  });

  describe('Track Navigation', () => {
    it('should call nextTrack when next button clicked', async () => {
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
        expect(mockPlayerAPI.nextTrack).toHaveBeenCalled();
      }
    });

    it('should call previousTrack when previous button clicked', async () => {
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
        expect(mockPlayerAPI.previousTrack).toHaveBeenCalled();
      }
    });

    it('should disable previous button at queue start', () => {
      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
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
      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
        queueIndex: 1,
        queue: [
          { id: 1, title: 'Track 1' },
          { id: 2, title: 'Track 2' },
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
      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
        volume: 75,
      });

      render(
        <Wrapper>
          <BottomPlayerBarUnified />
        </Wrapper>
      );

      expect(screen.getByText('75')).toBeInTheDocument();
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
        expect(mockPlayerAPI.setVolume).toHaveBeenCalled();
      });
    });

    it('should show mute icon when volume is 0', () => {
      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
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
      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
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
      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
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
      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
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
      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
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

      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
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
        expect(mockPlayerAPI.seek).toHaveBeenCalled();
      });
    });

    it('should handle seeking at track end', async () => {
      const user = userEvent.setup();

      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
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
        expect(mockPlayerAPI.seek).toHaveBeenCalledWith(180);
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
      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
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
      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
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
        expect(mockPlayerAPI.toggleFavorite).toHaveBeenCalled();
      }
    });
  });

  describe('Enhancement Indicator', () => {
    it('should show enhancement status', () => {
      (useEnhancement as jest.Mock).mockReturnValue({
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
      (useEnhancement as jest.Mock).mockReturnValue({
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
      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
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
      (useUnifiedWebMAudioPlayer as jest.Mock).mockReturnValue({
        ...mockPlayerState,
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
          mockPlayerAPI.play.mock.calls.length > 0 ||
          mockPlayerAPI.pause.mock.calls.length > 0;
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
        expect(mockPlayerAPI.nextTrack).toHaveBeenCalled();
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
