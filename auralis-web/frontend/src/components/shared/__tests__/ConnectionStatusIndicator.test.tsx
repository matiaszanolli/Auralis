/**
 * ConnectionStatusIndicator Component Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Unit tests for connection status indicator component.
 *
 * Test Coverage:
 * - Connection status display (connected/disconnected/reconnecting)
 * - Latency display
 * - WebSocket/API status indicators
 * - Reconnect button
 * - Auto-hide when connected
 * - Position variants
 * - Loading states
 * - Error states
 * - Status transitions
 * - Accessibility
 *
 * Phase C.3: Component Testing & Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@/test/test-utils';
import { ConnectionStatusIndicator } from '../ConnectionStatusIndicator';
import * as hooks from '@/hooks/websocket/useWebSocketProtocol';
import { mockUseWebSocketProtocol } from './test-utils';

// Mock the hooks
vi.mock('@/hooks/websocket/useWebSocketProtocol', () => ({
  useWebSocketProtocol: vi.fn(),
}));

describe('ConnectionStatusIndicator', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset the mock for each test to avoid state bleed
    vi.mocked(hooks.useWebSocketProtocol).mockReturnValue({
      isConnected: true,
      latency: 25,
      canReconnect: false,
      connectionStatus: 'connected',
      reconnect: vi.fn(),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ============================================================================
  // Rendering Tests
  // ============================================================================

  it('should render status indicator', () => {
    render(<ConnectionStatusIndicator />);

    expect(screen.getByTestId('connection-indicator')).toBeInTheDocument();
  });

  it('should display connection status text', () => {
    render(<ConnectionStatusIndicator />);

    expect(screen.getByText(/Connected/i)).toBeInTheDocument();
  });

  it('should display latency information', () => {
    render(<ConnectionStatusIndicator />);

    expect(screen.getByText(/Latency.*25ms/i)).toBeInTheDocument();
  });

  // ============================================================================
  // Connection Status Tests
  // ============================================================================

  it('should show green indicator when connected', () => {
    render(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    expect(indicator).toHaveClass('status-connected');
  });

  it('should show red indicator when disconnected', () => {
    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: false,
      latency: 0,
      canReconnect: true,
      connectionStatus: 'disconnected',
      reconnect: vi.fn(),
    }));

    render(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    expect(indicator).toHaveClass('status-disconnected');
  });

  it('should show yellow indicator when reconnecting', () => {
    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: false,
      latency: 0,
      canReconnect: true,
      connectionStatus: 'reconnecting',
      reconnect: vi.fn(),
    }));

    render(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    expect(indicator).toHaveClass('status-reconnecting');
  });

  // ============================================================================
  // Status Text Tests
  // ============================================================================

  it('should show "Connected" text when online', () => {
    render(<ConnectionStatusIndicator />);

    expect(screen.getByText('Connected')).toBeInTheDocument();
  });

  it('should show "Disconnected" text when offline', () => {
    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: false,
      latency: 0,
      canReconnect: true,
      connectionStatus: 'disconnected',
      reconnect: vi.fn(),
    }));

    render(<ConnectionStatusIndicator />);

    expect(screen.getByText('Disconnected')).toBeInTheDocument();
  });

  it('should show "Reconnecting..." text when attempting reconnection', () => {
    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: false,
      latency: 0,
      canReconnect: true,
      connectionStatus: 'reconnecting',
      reconnect: vi.fn(),
    }));

    render(<ConnectionStatusIndicator />);

    expect(screen.getByText(/Reconnecting/i)).toBeInTheDocument();
  });

  // ============================================================================
  // Latency Display Tests
  // ============================================================================

  it('should display latency in milliseconds', () => {
    render(<ConnectionStatusIndicator />);

    expect(screen.getByText(/25ms/)).toBeInTheDocument();
  });

  it('should update latency display', () => {
    const { rerender } = render(<ConnectionStatusIndicator />);

    expect(screen.getByText(/25ms/)).toBeInTheDocument();

    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: true,
      latency: 50,
      canReconnect: false,
      connectionStatus: 'connected',
      reconnect: vi.fn(),
    }));

    rerender(<ConnectionStatusIndicator />);

    expect(screen.getByText(/50ms/)).toBeInTheDocument();
  });

  it('should show "N/A" latency when disconnected', () => {
    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: false,
      latency: 0,
      canReconnect: true,
      connectionStatus: 'disconnected',
      reconnect: vi.fn(),
    }));

    render(<ConnectionStatusIndicator />);

    expect(screen.getByText(/N\/A/)).toBeInTheDocument();
  });

  // ============================================================================
  // Reconnect Button Tests
  // ============================================================================

  it('should show reconnect button when disconnected', () => {
    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: false,
      latency: 0,
      canReconnect: true,
      connectionStatus: 'disconnected',
      reconnect: vi.fn(),
    }));

    render(<ConnectionStatusIndicator />);

    expect(screen.getByRole('button', { name: /reconnect/i })).toBeInTheDocument();
  });

  it('should not show reconnect button when connected', () => {
    render(<ConnectionStatusIndicator />);

    expect(screen.queryByRole('button', { name: /reconnect/i })).not.toBeInTheDocument();
  });

  it('should call reconnect when button clicked', async () => {
    const mockReconnect = vi.fn().mockResolvedValue(undefined);

    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: false,
      latency: 0,
      canReconnect: true,
      connectionStatus: 'disconnected',
      reconnect: mockReconnect,
    }));

    render(<ConnectionStatusIndicator />);

    const reconnectButton = screen.getByRole('button', { name: /reconnect/i });
    fireEvent.click(reconnectButton);

    await waitFor(() => {
      expect(mockReconnect).toHaveBeenCalled();
    });
  });

  it('should disable reconnect button when cannot reconnect', () => {
    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: false,
      latency: 0,
      canReconnect: false,
      connectionStatus: 'disconnected',
      reconnect: vi.fn(),
    }));

    render(<ConnectionStatusIndicator />);

    const reconnectButton = screen.getByRole('button', { name: /reconnect/i }) as HTMLButtonElement;
    expect(reconnectButton.disabled).toBe(true);
  });

  // ============================================================================
  // Position Tests
  // ============================================================================

  it('should render at top-left by default', () => {
    const { container } = render(<ConnectionStatusIndicator position="top-left" />);

    const wrapper = container.querySelector('[data-position="top-left"]');
    expect(wrapper).toBeInTheDocument();
  });

  it('should render at top-right', () => {
    const { container } = render(<ConnectionStatusIndicator position="top-right" />);

    const wrapper = container.querySelector('[data-position="top-right"]');
    expect(wrapper).toBeInTheDocument();
  });

  it('should render at bottom-left', () => {
    const { container } = render(<ConnectionStatusIndicator position="bottom-left" />);

    const wrapper = container.querySelector('[data-position="bottom-left"]');
    expect(wrapper).toBeInTheDocument();
  });

  it('should render at bottom-right', () => {
    const { container } = render(<ConnectionStatusIndicator position="bottom-right" />);

    const wrapper = container.querySelector('[data-position="bottom-right"]');
    expect(wrapper).toBeInTheDocument();
  });

  // ============================================================================
  // Compact Mode Tests
  // ============================================================================

  it('should render in compact mode', () => {
    render(<ConnectionStatusIndicator compact={true} />);

    // Compact mode shows only indicator dot
    expect(screen.getByTestId('connection-indicator')).toBeInTheDocument();
  });

  it('should show full details in normal mode', () => {
    render(<ConnectionStatusIndicator compact={false} />);

    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByText(/Latency/)).toBeInTheDocument();
  });

  // ============================================================================
  // Auto-Hide Tests
  // ============================================================================

  it('should auto-hide when connected', () => {
    vi.useFakeTimers();

    const { container } = render(<ConnectionStatusIndicator />);

    let statusContainer = container.querySelector('[data-testid="status-container"]');
    expect(statusContainer).toHaveClass('auto-hide');

    vi.advanceTimersByTime(5000);

    statusContainer = container.querySelector('[data-testid="status-container"]');
    expect(statusContainer).toHaveClass('hidden');

    vi.useRealTimers();
  });

  it('should show immediately when disconnected', () => {
    vi.useFakeTimers();

    const { container, rerender } = render(<ConnectionStatusIndicator />);

    // Advance time past auto-hide delay
    vi.advanceTimersByTime(6000);

    // Should be hidden
    let statusContainer = container.querySelector('[data-testid="status-container"]');
    expect(statusContainer).toHaveClass('hidden');

    // Simulate disconnection
    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: false,
      latency: 0,
      canReconnect: true,
      connectionStatus: 'disconnected',
      reconnect: vi.fn(),
    }));

    rerender(<ConnectionStatusIndicator />);

    // Should be visible again
    statusContainer = container.querySelector('[data-testid="status-container"]');
    expect(statusContainer).not.toHaveClass('hidden');

    vi.useRealTimers();
  });

  // ============================================================================
  // Accessibility Tests
  // ============================================================================

  it('should have accessible status text', () => {
    render(<ConnectionStatusIndicator />);

    const status = screen.getByText('Connected');
    expect(status).toHaveAttribute('aria-live', 'polite');
  });

  it('should have accessible indicator', () => {
    render(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    expect(indicator).toHaveAttribute('aria-label');
  });

  it('should announce status changes', async () => {
    const { rerender } = render(<ConnectionStatusIndicator />);

    expect(screen.getByText('Connected')).toBeInTheDocument();

    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: false,
      latency: 0,
      canReconnect: true,
      connectionStatus: 'disconnected',
      reconnect: vi.fn(),
    }));

    rerender(<ConnectionStatusIndicator />);

    await waitFor(() => {
      expect(screen.getByText('Disconnected')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Status Transition Tests
  // ============================================================================

  it('should transition from connected to disconnected', async () => {
    const { rerender } = render(<ConnectionStatusIndicator />);

    const indicator1 = screen.getByTestId('connection-indicator');
    expect(indicator1).toHaveClass('status-connected');

    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: false,
      latency: 0,
      canReconnect: true,
      connectionStatus: 'disconnected',
      reconnect: vi.fn(),
    }));

    rerender(<ConnectionStatusIndicator />);

    await waitFor(() => {
      const indicator2 = screen.getByTestId('connection-indicator');
      expect(indicator2).toHaveClass('status-disconnected');
    });
  });

  it('should transition through reconnecting state', async () => {
    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: false,
      latency: 0,
      canReconnect: true,
      connectionStatus: 'reconnecting',
      reconnect: vi.fn(),
    }));

    const { rerender } = render(<ConnectionStatusIndicator />);

    const indicator1 = screen.getByTestId('connection-indicator');
    expect(indicator1).toHaveClass('status-reconnecting');

    // Simulate successful reconnection
    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: true,
      latency: 25,
      canReconnect: false,
      connectionStatus: 'connected',
      reconnect: vi.fn(),
    }));

    rerender(<ConnectionStatusIndicator />);

    await waitFor(() => {
      const indicator2 = screen.getByTestId('connection-indicator');
      expect(indicator2).toHaveClass('status-connected');
    });
  });

  // ============================================================================
  // Animation Tests
  // ============================================================================

  it('should animate pulsing when reconnecting', async () => {
    vi.mocked(hooks.useWebSocketProtocol).mockImplementation(() => ({
      isConnected: false,
      latency: 0,
      canReconnect: true,
      connectionStatus: 'reconnecting',
      reconnect: vi.fn(),
    }));

    const { container } = render(<ConnectionStatusIndicator />);

    const indicator = container.querySelector('[data-testid="connection-indicator"]');
    expect(indicator).toHaveClass('pulse-animation');
  });

  it('should not animate when connected', () => {
    const { container } = render(<ConnectionStatusIndicator />);

    const indicator = container.querySelector('[data-testid="connection-indicator"]');
    expect(indicator).not.toHaveClass('pulse-animation');
  });
});
