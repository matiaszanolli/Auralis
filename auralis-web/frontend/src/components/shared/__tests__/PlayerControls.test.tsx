/**
 * PlayerControls Component Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Unit tests for player controls component.
 *
 * Test Coverage:
 * - Play/pause toggle
 * - Seek functionality
 * - Next/previous navigation
 * - Volume control
 * - Mute button
 * - Preset selection
 * - Time display
 * - Loading states
 * - Disabled states
 * - Current track display
 * - Error handling
 *
 * Phase C.3: Component Testing & Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@/test/test-utils';
import { PlayerControls } from '../PlayerControls';
import * as hooks from '@/hooks/websocket/useWebSocketProtocol';
import * as playerHooks from '@/hooks/websocket/useWebSocketProtocol';
import {
  mockUsePlayerCommands,
  mockUsePlayerStateUpdates,
  mockTrack,
} from './test-utils';

// Mock the hooks
vi.mock('@/hooks/websocket/useWebSocketProtocol', () => ({
  usePlayerCommands: vi.fn(),
  usePlayerStateUpdates: vi.fn(),
}));

describe('PlayerControls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (hooks.usePlayerCommands as any).mockImplementation(mockUsePlayerCommands());
    (playerHooks.usePlayerStateUpdates as any).mockImplementation(mockUsePlayerStateUpdates());
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ============================================================================
  // Rendering Tests
  // ============================================================================

  it('should render play/pause button', () => {
    render(<PlayerControls />);

    const playButton = screen.getByRole('button', { name: /play/i });
    expect(playButton).toBeInTheDocument();
  });

  it('should render next/previous buttons', () => {
    render(<PlayerControls />);

    expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
  });

  it('should render volume slider', () => {
    render(<PlayerControls />);

    const volumeSlider = screen.getByRole('slider', { name: /volume/i });
    expect(volumeSlider).toBeInTheDocument();
  });

  it('should render time display', () => {
    render(<PlayerControls />);

    expect(screen.getByText(/0:00.*5:30/)).toBeInTheDocument();
  });

  it('should render current track info', () => {
    render(<PlayerControls />);

    expect(screen.getByText('Test Track')).toBeInTheDocument();
    expect(screen.getByText('Test Artist')).toBeInTheDocument();
  });

  it('should render preset selector when enabled', () => {
    render(<PlayerControls showPresetSelector={true} />);

    expect(screen.getByRole('combobox', { name: /preset/i })).toBeInTheDocument();
  });

  // ============================================================================
  // Play/Pause Tests
  // ============================================================================

  it('should toggle play state when play button clicked', async () => {
    const mockPlayPause = vi.fn().mockResolvedValue(undefined);

    (hooks.usePlayerCommands as any).mockImplementation(() => ({
      playPause: mockPlayPause,
      next: vi.fn(),
      previous: vi.fn(),
      seek: vi.fn(),
      setVolume: vi.fn(),
      setMuted: vi.fn(),
      setPreset: vi.fn(),
      loading: false,
      error: null,
    }));

    render(<PlayerControls />);

    const playButton = screen.getByRole('button', { name: /play/i });
    fireEvent.click(playButton);

    await waitFor(() => {
      expect(mockPlayPause).toHaveBeenCalled();
    });
  });

  it('should show pause icon when playing', () => {
    (playerHooks.usePlayerStateUpdates as any).mockImplementation(() => ({
      isPlaying: true,
      currentTrack: mockTrack(),
      currentTime: 0,
      duration: 330,
      volume: 70,
      isMuted: false,
      preset: 'adaptive',
    }));

    render(<PlayerControls />);

    expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
  });

  // ============================================================================
  // Seek Tests
  // ============================================================================

  it('should update current time when seeking', async () => {
    const mockSeek = vi.fn().mockResolvedValue(undefined);

    (hooks.usePlayerCommands as any).mockImplementation(() => ({
      playPause: vi.fn(),
      next: vi.fn(),
      previous: vi.fn(),
      seek: mockSeek,
      setVolume: vi.fn(),
      setMuted: vi.fn(),
      setPreset: vi.fn(),
      loading: false,
      error: null,
    }));

    render(<PlayerControls />);

    const progressBar = screen.getByRole('slider', { name: /progress/i });
    fireEvent.change(progressBar, { target: { value: '165' } });

    await waitFor(() => {
      expect(mockSeek).toHaveBeenCalledWith(expect.any(Number));
    });
  });

  it('should display updated time after seek', async () => {
    (playerHooks.usePlayerStateUpdates as any).mockImplementation(() => ({
      isPlaying: false,
      currentTrack: mockTrack(),
      currentTime: 165,
      duration: 330,
      volume: 70,
      isMuted: false,
      preset: 'adaptive',
    }));

    render(<PlayerControls />);

    expect(screen.getByText(/2:45.*5:30/)).toBeInTheDocument();
  });

  // ============================================================================
  // Navigation Tests
  // ============================================================================

  it('should go to next track when next button clicked', async () => {
    const mockNext = vi.fn().mockResolvedValue(undefined);

    (hooks.usePlayerCommands as any).mockImplementation(() => ({
      playPause: vi.fn(),
      next: mockNext,
      previous: vi.fn(),
      seek: vi.fn(),
      setVolume: vi.fn(),
      setMuted: vi.fn(),
      setPreset: vi.fn(),
      loading: false,
      error: null,
    }));

    render(<PlayerControls />);

    const nextButton = screen.getByRole('button', { name: /next/i });
    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(mockNext).toHaveBeenCalled();
    });
  });

  it('should go to previous track when previous button clicked', async () => {
    const mockPrevious = vi.fn().mockResolvedValue(undefined);

    (hooks.usePlayerCommands as any).mockImplementation(() => ({
      playPause: vi.fn(),
      next: vi.fn(),
      previous: mockPrevious,
      seek: vi.fn(),
      setVolume: vi.fn(),
      setMuted: vi.fn(),
      setPreset: vi.fn(),
      loading: false,
      error: null,
    }));

    render(<PlayerControls />);

    const prevButton = screen.getByRole('button', { name: /previous/i });
    fireEvent.click(prevButton);

    await waitFor(() => {
      expect(mockPrevious).toHaveBeenCalled();
    });
  });

  // ============================================================================
  // Volume Tests
  // ============================================================================

  it('should update volume when slider moved', async () => {
    const mockSetVolume = vi.fn().mockResolvedValue(undefined);

    (hooks.usePlayerCommands as any).mockImplementation(() => ({
      playPause: vi.fn(),
      next: vi.fn(),
      previous: vi.fn(),
      seek: vi.fn(),
      setVolume: mockSetVolume,
      setMuted: vi.fn(),
      setPreset: vi.fn(),
      loading: false,
      error: null,
    }));

    render(<PlayerControls />);

    const volumeSlider = screen.getByRole('slider', { name: /volume/i });
    fireEvent.change(volumeSlider, { target: { value: '50' } });

    await waitFor(() => {
      expect(mockSetVolume).toHaveBeenCalledWith(50);
    });
  });

  it('should display current volume level', () => {
    (playerHooks.usePlayerStateUpdates as any).mockImplementation(() => ({
      isPlaying: false,
      currentTrack: mockTrack(),
      currentTime: 0,
      duration: 330,
      volume: 50,
      isMuted: false,
      preset: 'adaptive',
    }));

    render(<PlayerControls />);

    const volumeSlider = screen.getByRole('slider', { name: /volume/i }) as HTMLInputElement;
    expect(volumeSlider.value).toBe('50');
  });

  // ============================================================================
  // Mute Tests
  // ============================================================================

  it('should toggle mute when mute button clicked', async () => {
    const mockSetMuted = vi.fn().mockResolvedValue(undefined);

    (hooks.usePlayerCommands as any).mockImplementation(() => ({
      playPause: vi.fn(),
      next: vi.fn(),
      previous: vi.fn(),
      seek: vi.fn(),
      setVolume: vi.fn(),
      setMuted: mockSetMuted,
      setPreset: vi.fn(),
      loading: false,
      error: null,
    }));

    render(<PlayerControls />);

    const muteButton = screen.getByRole('button', { name: /mute/i });
    fireEvent.click(muteButton);

    await waitFor(() => {
      expect(mockSetMuted).toHaveBeenCalled();
    });
  });

  it('should show unmute icon when muted', () => {
    (playerHooks.usePlayerStateUpdates as any).mockImplementation(() => ({
      isPlaying: false,
      currentTrack: mockTrack(),
      currentTime: 0,
      duration: 330,
      volume: 70,
      isMuted: true,
      preset: 'adaptive',
    }));

    render(<PlayerControls />);

    expect(screen.getByRole('button', { name: /unmute/i })).toBeInTheDocument();
  });

  // ============================================================================
  // Preset Tests
  // ============================================================================

  it('should change preset when selected', async () => {
    const mockSetPreset = vi.fn().mockResolvedValue(undefined);

    (hooks.usePlayerCommands as any).mockImplementation(() => ({
      playPause: vi.fn(),
      next: vi.fn(),
      previous: vi.fn(),
      seek: vi.fn(),
      setVolume: vi.fn(),
      setMuted: vi.fn(),
      setPreset: mockSetPreset,
      loading: false,
      error: null,
    }));

    render(<PlayerControls showPresetSelector={true} />);

    const presetSelector = screen.getByRole('combobox', { name: /preset/i });
    fireEvent.change(presetSelector, { target: { value: 'warm' } });

    await waitFor(() => {
      expect(mockSetPreset).toHaveBeenCalledWith('warm');
    });
  });

  it('should display current preset', () => {
    (playerHooks.usePlayerStateUpdates as any).mockImplementation(() => ({
      isPlaying: false,
      currentTrack: mockTrack(),
      currentTime: 0,
      duration: 330,
      volume: 70,
      isMuted: false,
      preset: 'bright',
    }));

    render(<PlayerControls showPresetSelector={true} />);

    const presetSelector = screen.getByRole('combobox', { name: /preset/i }) as HTMLSelectElement;
    expect(presetSelector.value).toBe('bright');
  });

  // ============================================================================
  // State Tests
  // ============================================================================

  it('should disable controls when loading', () => {
    (hooks.usePlayerCommands as any).mockImplementation(() => ({
      playPause: vi.fn(),
      next: vi.fn(),
      previous: vi.fn(),
      seek: vi.fn(),
      setVolume: vi.fn(),
      setMuted: vi.fn(),
      setPreset: vi.fn(),
      loading: true,
      error: null,
    }));

    render(<PlayerControls />);

    const playButton = screen.getByRole('button', { name: /play/i }) as HTMLButtonElement;
    expect(playButton.disabled).toBe(true);
  });

  it('should disable all controls when disabled prop is true', () => {
    render(<PlayerControls disabled={true} />);

    const playButton = screen.getByRole('button', { name: /play/i }) as HTMLButtonElement;
    expect(playButton.disabled).toBe(true);
  });

  it('should show error message when error occurs', () => {
    (hooks.usePlayerCommands as any).mockImplementation(() => ({
      playPause: vi.fn(),
      next: vi.fn(),
      previous: vi.fn(),
      seek: vi.fn(),
      setVolume: vi.fn(),
      setMuted: vi.fn(),
      setPreset: vi.fn(),
      loading: false,
      error: 'Playback failed',
    }));

    render(<PlayerControls />);

    expect(screen.getByText(/Playback failed/)).toBeInTheDocument();
  });

  // ============================================================================
  // Compact Mode Tests
  // ============================================================================

  it('should render in compact mode', () => {
    render(<PlayerControls compact={true} />);

    expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
    // Compact mode hides time display
    expect(screen.queryByText(/0:00.*5:30/)).not.toBeInTheDocument();
  });

  it('should render full controls in normal mode', () => {
    render(<PlayerControls />);

    expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
    expect(screen.getByText(/0:00.*5:30/)).toBeInTheDocument();
  });
});
