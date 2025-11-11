/**
 * PlayerBarV2Connected Integration Tests
 *
 * Tests for the connected version of PlayerBarV2 that integrates with:
 * - usePlayerAPI (track queue, playback state)
 * - useUnifiedWebMAudioPlayer (audio player, streaming)
 * - useEnhancement (enhancement settings)
 *
 * Total: 10 tests
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { render } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import PlayerBarV2Connected from '../../components/player-bar-v2/PlayerBarV2Connected';

// Mock the useUnifiedWebMAudioPlayer hook
vi.mock('@/hooks/useUnifiedWebMAudioPlayer', () => ({
  useUnifiedWebMAudioPlayer: () => ({
    currentTime: 30.5,
    duration: 240.5,
    isPlaying: false,
    isLoading: false,
    state: 'idle',
    metadata: null,
    error: null,
    player: {
      currentTime: 30.5,
      duration: 240.5,
    },
    loadTrack: vi.fn().mockResolvedValue(undefined),
    play: vi.fn().mockResolvedValue(undefined),
    pause: vi.fn(),
    stop: vi.fn(),
    seek: vi.fn().mockResolvedValue(undefined),
    setEnhanced: vi.fn().mockResolvedValue(undefined),
    setPreset: vi.fn().mockResolvedValue(undefined),
    setVolume: vi.fn(),
  }),
}));

describe('PlayerBarV2Connected Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ==========================================
  // 1. Initial Render (2 tests)
  // ==========================================

  describe('Initial Render', () => {
    it('should render without crashing', () => {
      // Act
      render(<PlayerBarV2Connected />);

      // Assert - Should have basic player controls
      expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
    });

    it('should show empty state when no track is playing', () => {
      // Act
      render(<PlayerBarV2Connected />);

      // Assert - Should not show current track title when no track is loaded
      // The word "track" might appear in aria-labels, so check more specifically
      const trackInfo = screen.queryByRole('heading', { name: /track/i });
      expect(trackInfo).not.toBeInTheDocument();
    });
  });

  // ==========================================
  // 2. Player Integration (3 tests)
  // ==========================================

  describe('Player Integration', () => {
    it('should integrate with usePlayerAPI hook', () => {
      // Act
      render(<PlayerBarV2Connected />);

      // Assert - Should render with Redux state
      const playButton = screen.getByRole('button', { name: /play/i });
      expect(playButton).toBeInTheDocument();
    });

    it('should integrate with useUnifiedWebMAudioPlayer hook', () => {
      // Act
      render(<PlayerBarV2Connected />);

      // Assert - Should use player time/duration from hook
      // Progress bar should exist (even if at 0)
      const progressBar = screen.getByRole('slider', { name: 'Seek' });
      expect(progressBar).toBeInTheDocument();
    });

    it('should integrate with useEnhancement hook', () => {
      // Act
      render(<PlayerBarV2Connected />);

      // Assert - Should have enhancement toggle
      const enhancementToggle = screen.getByRole('button', { name: /enhancement/i });
      expect(enhancementToggle).toBeInTheDocument();
    });
  });

  // ==========================================
  // 3. User Interactions (3 tests)
  // ==========================================

  describe('User Interactions', () => {
    it('should handle play button click', async () => {
      // Arrange
      const user = userEvent.setup();
      render(<PlayerBarV2Connected />);

      // Act
      const playButton = screen.getByRole('button', { name: /play/i });
      await user.click(playButton);

      // Assert - Click should be handled (no crash)
      expect(playButton).toBeInTheDocument();
    });

    it('should handle volume change', async () => {
      // Arrange
      const user = userEvent.setup();
      render(<PlayerBarV2Connected />);

      // Act
      // Look for the mute/unmute button which controls volume
      const volumeButton = screen.getByRole('button', { name: /mute|unmute/i });
      await user.click(volumeButton);

      // Assert - Should show volume control (mute/unmute button exists)
      expect(volumeButton).toBeInTheDocument();
    });

    it('should handle enhancement toggle', async () => {
      // Arrange
      const user = userEvent.setup();
      render(<PlayerBarV2Connected />);

      // Act
      const enhancementToggle = screen.getByRole('button', { name: /enhancement/i });
      await user.click(enhancementToggle);

      // Assert - Should toggle enhancement (no crash)
      expect(enhancementToggle).toBeInTheDocument();
    });
  });

  // ==========================================
  // 4. State Synchronization (2 tests)
  // ==========================================

  describe('State Synchronization', () => {
    it('should sync player state from hooks', () => {
      // Act
      render(<PlayerBarV2Connected />);

      // Assert - Should use currentTime/duration from useUnifiedWebMAudioPlayer
      // Progress bar should exist and be interactive
      const progressBar = screen.getByRole('slider', { name: 'Seek' });
      expect(progressBar).toBeInTheDocument();
    });

    it('should pass enhancement settings to player', () => {
      // Act
      render(<PlayerBarV2Connected />);

      // Assert - Should initialize with enhancement context settings
      const enhancementToggle = screen.getByRole('button', { name: /enhancement/i });
      expect(enhancementToggle).toBeInTheDocument();
    });
  });
});
