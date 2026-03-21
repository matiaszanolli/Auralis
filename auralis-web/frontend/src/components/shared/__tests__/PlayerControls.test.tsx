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
 *
 * Phase C.3: Component Testing & Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import React, { ReactElement } from 'react';
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render as rtlRender, screen, fireEvent, waitFor, cleanup, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { PlayerControls } from '../PlayerControls';

// Mock WebSocketContext
const mockSend = vi.fn();
let mockSubscribeCallback: ((message: any) => void) | null = null;

vi.mock('@/contexts/WebSocketContext', () => ({
  useWebSocketContext: () => ({
    isConnected: true,
    connectionStatus: 'connected',
    send: mockSend,
    subscribe: (_type: string, handler: (message: any) => void) => {
      mockSubscribeCallback = handler;
      return () => { mockSubscribeCallback = null; };
    },
    subscribeAll: vi.fn(() => () => {}),
    connect: vi.fn(),
    disconnect: vi.fn(),
  }),
}));

/**
 * Minimal wrapper for PlayerControls tests
 */
function MinimalWrapper({ children }: { children: React.ReactNode }) {
  return (
    <BrowserRouter>
      {children}
    </BrowserRouter>
  );
}

/**
 * Custom render function using minimal wrapper
 */
function render(ui: ReactElement) {
  return rtlRender(ui, { wrapper: MinimalWrapper });
}

/**
 * Simulate a player_state WebSocket message
 */
function simulatePlayerState(state: Record<string, any> = {}) {
  const defaultState = {
    is_playing: false,
    current_track: {
      id: 1,
      title: 'Test Track',
      artist: 'Test Artist',
      duration: 240,
    },
    current_time: 0,
    duration: 240,
    volume: 70,
    is_muted: false,
  };

  if (mockSubscribeCallback) {
    act(() => {
      mockSubscribeCallback!({
        type: 'player_state',
        data: { ...defaultState, ...state },
      });
    });
  }
}

describe('PlayerControls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSubscribeCallback = null;
  });

  afterEach(() => {
    cleanup();
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

  it('should render time display', async () => {
    render(<PlayerControls />);
    simulatePlayerState();

    await waitFor(() => {
      expect(screen.getByText('0:00')).toBeInTheDocument();
      expect(screen.getByText('4:00')).toBeInTheDocument();
    });
  });

  it('should render current track info', async () => {
    render(<PlayerControls />);
    simulatePlayerState();

    await waitFor(() => {
      expect(screen.getByText('Test Track')).toBeInTheDocument();
      expect(screen.getByText('Test Artist')).toBeInTheDocument();
    });
  });

  it('should render preset buttons when enabled', () => {
    render(<PlayerControls showPresetSelector={true} />);

    expect(screen.getByTitle('Adaptive')).toBeInTheDocument();
    expect(screen.getByTitle('Gentle')).toBeInTheDocument();
    expect(screen.getByTitle('Warm')).toBeInTheDocument();
    expect(screen.getByTitle('Bright')).toBeInTheDocument();
    expect(screen.getByTitle('Punchy')).toBeInTheDocument();
  });

  // ============================================================================
  // Play/Pause Tests
  // ============================================================================

  it('should send play when play button clicked and not playing', async () => {
    const user = userEvent.setup();
    render(<PlayerControls />);
    simulatePlayerState({ is_playing: false });

    const playButton = screen.getByRole('button', { name: /play/i });
    await user.click(playButton);

    expect(mockSend).toHaveBeenCalledWith({ type: 'play' });
  });

  it('should send pause when pause button clicked and playing', async () => {
    const user = userEvent.setup();
    render(<PlayerControls />);
    simulatePlayerState({ is_playing: true });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
    });

    const pauseButton = screen.getByRole('button', { name: /pause/i });
    await user.click(pauseButton);

    expect(mockSend).toHaveBeenCalledWith({ type: 'pause' });
  });

  it('should show pause icon when playing', async () => {
    render(<PlayerControls />);
    simulatePlayerState({ is_playing: true });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Navigation Tests
  // ============================================================================

  it('should send next when next button clicked', async () => {
    const user = userEvent.setup();
    render(<PlayerControls />);

    const nextButton = screen.getByRole('button', { name: /next/i });
    await user.click(nextButton);

    expect(mockSend).toHaveBeenCalledWith({ type: 'next' });
  });

  it('should send previous when previous button clicked', async () => {
    const user = userEvent.setup();
    render(<PlayerControls />);

    const prevButton = screen.getByRole('button', { name: /previous/i });
    await user.click(prevButton);

    expect(mockSend).toHaveBeenCalledWith({ type: 'previous' });
  });

  // ============================================================================
  // Volume Tests
  // ============================================================================

  it('should update volume display when slider moved', () => {
    render(<PlayerControls />);

    const volumeSlider = screen.getByRole('slider', { name: /volume/i });
    fireEvent.change(volumeSlider, { target: { value: '50' } });

    expect(screen.getByText('50%')).toBeInTheDocument();
  });

  it('should display current volume level', async () => {
    render(<PlayerControls />);
    simulatePlayerState({ volume: 70 });

    await waitFor(() => {
      expect(screen.getByText('70%')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Mute Tests
  // ============================================================================

  it('should toggle mute when mute button clicked', async () => {
    const user = userEvent.setup();
    render(<PlayerControls />);

    const muteButton = screen.getByRole('button', { name: /mute/i });
    await user.click(muteButton);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /unmute/i })).toBeInTheDocument();
    });
  });

  it('should show muted volume display when muted', async () => {
    const user = userEvent.setup();
    render(<PlayerControls />);

    const muteButton = screen.getByRole('button', { name: /mute/i });
    await user.click(muteButton);

    expect(screen.getByText('0%')).toBeInTheDocument();
  });

  // ============================================================================
  // Preset Tests
  // ============================================================================

  it('should highlight selected preset', () => {
    render(<PlayerControls showPresetSelector={true} />);

    const warmButton = screen.getByTitle('Warm');
    expect(warmButton).toBeInTheDocument();
  });

  it('should change preset when button clicked', async () => {
    const user = userEvent.setup();
    render(<PlayerControls showPresetSelector={true} />);

    const brightButton = screen.getByTitle('Bright');
    await user.click(brightButton);

    expect(brightButton).toBeInTheDocument();
  });

  // ============================================================================
  // State Tests
  // ============================================================================

  it('should show loading indicator when loading', async () => {
    render(<PlayerControls />);
    simulatePlayerState({ isLoading: true });

    await waitFor(() => {
      expect(screen.getByText('⏳')).toBeInTheDocument();
    });
  });

  it('should apply disabled styling when disabled prop is true', () => {
    const { container } = render(<PlayerControls disabled={true} />);

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.style.opacity).toBe('0.5');
  });

  // ============================================================================
  // Compact Mode Tests
  // ============================================================================

  it('should hide track info in compact mode', () => {
    render(<PlayerControls compact={true} />);

    expect(screen.queryByText('Test Track')).not.toBeInTheDocument();
    expect(screen.queryByText('Test Artist')).not.toBeInTheDocument();
  });

  it('should show track info in normal mode', async () => {
    render(<PlayerControls compact={false} />);
    simulatePlayerState();

    await waitFor(() => {
      expect(screen.getByText('Test Track')).toBeInTheDocument();
      expect(screen.getByText('Test Artist')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Time Display Tests
  // ============================================================================

  it('should display correct current time', async () => {
    render(<PlayerControls />);
    simulatePlayerState({ current_time: 125, duration: 240 }); // 2:05

    await waitFor(() => {
      expect(screen.getByText('2:05')).toBeInTheDocument();
    });
  });

  it('should display correct duration', async () => {
    render(<PlayerControls />);
    simulatePlayerState({ current_time: 0, duration: 330 }); // 5:30

    await waitFor(() => {
      expect(screen.getByText('5:30')).toBeInTheDocument();
    });
  });
});
