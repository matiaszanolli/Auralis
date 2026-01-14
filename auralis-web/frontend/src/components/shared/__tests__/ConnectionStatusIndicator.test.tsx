/**
 * ConnectionStatusIndicator Component Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Unit tests for connection status indicator component.
 *
 * Test Coverage:
 * - Connection status display (connected/disconnected/reconnecting)
 * - Position variants
 * - Compact mode
 * - Details expansion on hover/click
 * - Status transitions
 *
 * Phase C.3: Component Testing & Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import React from 'react';
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { ConnectionStatusIndicator } from '../ConnectionStatusIndicator';
import * as hooks from '@/hooks/websocket/useWebSocketProtocol';

// Mock the hooks
vi.mock('@/hooks/websocket/useWebSocketProtocol', () => ({
  useWebSocketProtocol: vi.fn(),
}));

// Mock fetch for latency measurements
global.fetch = vi.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ status: 'ok' }),
  })
) as any;

/**
 * Minimal wrapper that avoids WebSocket singleton issues
 */
function MinimalWrapper({ children }: { children: React.ReactNode }) {
  return (
    <BrowserRouter>
      <ThemeProvider>
        {children}
      </ThemeProvider>
    </BrowserRouter>
  );
}

/**
 * Custom render with MinimalWrapper
 */
function renderWithMinimalWrapper(ui: React.ReactElement) {
  return render(ui, { wrapper: MinimalWrapper });
}

describe('ConnectionStatusIndicator', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset the mock for each test to avoid state bleed
    vi.mocked(hooks.useWebSocketProtocol).mockReturnValue({
      connected: true,
      error: undefined,
      send: vi.fn(),
      subscribe: vi.fn(),
      disconnect: vi.fn(),
      reconnect: vi.fn(),
    } as any);
  });

  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  // ============================================================================
  // Rendering Tests
  // ============================================================================

  it('should render status indicator', () => {
    renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    expect(screen.getByTestId('connection-indicator')).toBeInTheDocument();
  });

  it('should render with connected status attribute when WebSocket connected', () => {
    renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    expect(indicator).toHaveAttribute('data-status', 'connected');
  });

  it('should render with disconnected status when not connected and no error', () => {
    vi.mocked(hooks.useWebSocketProtocol).mockReturnValue({
      connected: false,
      error: undefined,
      send: vi.fn(),
      subscribe: vi.fn(),
      disconnect: vi.fn(),
      reconnect: vi.fn(),
    } as any);

    renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    expect(indicator).toHaveAttribute('data-status', 'disconnected');
  });

  it('should render with reconnecting status when error and not connected', () => {
    vi.mocked(hooks.useWebSocketProtocol).mockReturnValue({
      connected: false,
      error: new Error('Connection lost'),
      send: vi.fn(),
      subscribe: vi.fn(),
      disconnect: vi.fn(),
      reconnect: vi.fn(),
    } as any);

    renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    expect(indicator).toHaveAttribute('data-status', 'reconnecting');
  });

  // ============================================================================
  // Compact Mode Tests
  // ============================================================================

  it('should return null in compact mode when connected', () => {
    const { container } = renderWithMinimalWrapper(<ConnectionStatusIndicator compact={true} />);

    // In compact mode, component returns null when connected
    expect(container.querySelector('[data-testid="connection-indicator"]')).toBeNull();
  });

  it('should render in compact mode when disconnected', () => {
    vi.mocked(hooks.useWebSocketProtocol).mockReturnValue({
      connected: false,
      error: undefined,
      send: vi.fn(),
      subscribe: vi.fn(),
      disconnect: vi.fn(),
      reconnect: vi.fn(),
    } as any);

    renderWithMinimalWrapper(<ConnectionStatusIndicator compact={true} />);

    expect(screen.getByTestId('connection-indicator')).toBeInTheDocument();
  });

  it('should render in non-compact mode when connected', () => {
    renderWithMinimalWrapper(<ConnectionStatusIndicator compact={false} />);

    expect(screen.getByTestId('connection-indicator')).toBeInTheDocument();
  });

  // ============================================================================
  // Position Tests (inline styles, not data attributes)
  // ============================================================================

  it('should render with default bottom-right position', () => {
    renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    // Component uses inline styles for position
    expect(indicator).toHaveStyle({ position: 'fixed' });
  });

  it('should accept position prop', () => {
    renderWithMinimalWrapper(<ConnectionStatusIndicator position="top-left" />);

    const indicator = screen.getByTestId('connection-indicator');
    expect(indicator).toHaveStyle({ position: 'fixed' });
  });

  // ============================================================================
  // Details Expansion Tests
  // ============================================================================

  it('should show expanded details on mouse enter', async () => {
    renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    fireEvent.mouseEnter(indicator);

    // After mouse enter, expanded details should appear
    await waitFor(() => {
      expect(screen.getByText('WebSocket')).toBeInTheDocument();
    });
  });

  it('should hide details on mouse leave', async () => {
    renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');

    // Show details
    fireEvent.mouseEnter(indicator);
    await waitFor(() => {
      expect(screen.getByText('WebSocket')).toBeInTheDocument();
    });

    // Hide details
    fireEvent.mouseLeave(indicator);
    await waitFor(() => {
      expect(screen.queryByText('WebSocket')).not.toBeInTheDocument();
    });
  });

  it('should toggle details on click', async () => {
    renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    // Click the compact indicator (the circular div inside)
    const clickableArea = indicator.querySelector('div');
    if (clickableArea) {
      fireEvent.click(clickableArea);
    }

    // Details should show after click
    await waitFor(() => {
      expect(screen.getByText('WebSocket')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // WebSocket Status Display Tests
  // ============================================================================

  it('should show WebSocket as connected in details', async () => {
    renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    fireEvent.mouseEnter(indicator);

    await waitFor(() => {
      // Find all "Connected" texts - one for overall status, one for WebSocket
      const connectedTexts = screen.getAllByText('Connected');
      expect(connectedTexts.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('should show WebSocket as disconnected in details', async () => {
    vi.mocked(hooks.useWebSocketProtocol).mockReturnValue({
      connected: false,
      error: undefined,
      send: vi.fn(),
      subscribe: vi.fn(),
      disconnect: vi.fn(),
      reconnect: vi.fn(),
    } as any);

    renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    fireEvent.mouseEnter(indicator);

    await waitFor(() => {
      const disconnectedTexts = screen.getAllByText('Disconnected');
      expect(disconnectedTexts.length).toBeGreaterThanOrEqual(1);
    });
  });

  // ============================================================================
  // Status Transition Tests
  // ============================================================================

  it('should transition from connected to disconnected', async () => {
    const { rerender } = renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    expect(screen.getByTestId('connection-indicator')).toHaveAttribute('data-status', 'connected');

    vi.mocked(hooks.useWebSocketProtocol).mockReturnValue({
      connected: false,
      error: undefined,
      send: vi.fn(),
      subscribe: vi.fn(),
      disconnect: vi.fn(),
      reconnect: vi.fn(),
    } as any);

    // Rerender just the component - wrapper is already applied
    rerender(<ConnectionStatusIndicator />);

    await waitFor(() => {
      expect(screen.getByTestId('connection-indicator')).toHaveAttribute('data-status', 'disconnected');
    });
  });

  it('should transition from disconnected to reconnecting', async () => {
    vi.mocked(hooks.useWebSocketProtocol).mockReturnValue({
      connected: false,
      error: undefined,
      send: vi.fn(),
      subscribe: vi.fn(),
      disconnect: vi.fn(),
      reconnect: vi.fn(),
    } as any);

    const { rerender } = renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    expect(screen.getByTestId('connection-indicator')).toHaveAttribute('data-status', 'disconnected');

    vi.mocked(hooks.useWebSocketProtocol).mockReturnValue({
      connected: false,
      error: new Error('Attempting reconnect'),
      send: vi.fn(),
      subscribe: vi.fn(),
      disconnect: vi.fn(),
      reconnect: vi.fn(),
    } as any);

    // Rerender just the component - wrapper is already applied
    rerender(<ConnectionStatusIndicator />);

    await waitFor(() => {
      expect(screen.getByTestId('connection-indicator')).toHaveAttribute('data-status', 'reconnecting');
    });
  });

  it('should transition from reconnecting to connected', async () => {
    vi.mocked(hooks.useWebSocketProtocol).mockReturnValue({
      connected: false,
      error: new Error('Reconnecting'),
      send: vi.fn(),
      subscribe: vi.fn(),
      disconnect: vi.fn(),
      reconnect: vi.fn(),
    } as any);

    const { rerender } = renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    expect(screen.getByTestId('connection-indicator')).toHaveAttribute('data-status', 'reconnecting');

    vi.mocked(hooks.useWebSocketProtocol).mockReturnValue({
      connected: true,
      error: undefined,
      send: vi.fn(),
      subscribe: vi.fn(),
      disconnect: vi.fn(),
      reconnect: vi.fn(),
    } as any);

    // Rerender just the component - wrapper is already applied
    rerender(<ConnectionStatusIndicator />);

    await waitFor(() => {
      expect(screen.getByTestId('connection-indicator')).toHaveAttribute('data-status', 'connected');
    });
  });

  // ============================================================================
  // Reconnect Button Tests
  // ============================================================================

  it('should show reconnect button when reconnecting and details expanded', async () => {
    vi.mocked(hooks.useWebSocketProtocol).mockReturnValue({
      connected: false,
      error: new Error('Connection lost'),
      send: vi.fn(),
      subscribe: vi.fn(),
      disconnect: vi.fn(),
      reconnect: vi.fn(),
    } as any);

    renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    fireEvent.mouseEnter(indicator);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /reconnect/i })).toBeInTheDocument();
    });
  });

  it('should not show reconnect button when connected', async () => {
    renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    fireEvent.mouseEnter(indicator);

    await waitFor(() => {
      expect(screen.getByText('WebSocket')).toBeInTheDocument();
    });

    expect(screen.queryByRole('button', { name: /reconnect/i })).not.toBeInTheDocument();
  });

  // ============================================================================
  // Error Display Tests
  // ============================================================================

  it('should display error message when error exists and details expanded', async () => {
    vi.mocked(hooks.useWebSocketProtocol).mockReturnValue({
      connected: false,
      error: new Error('Connection timeout'),
      send: vi.fn(),
      subscribe: vi.fn(),
      disconnect: vi.fn(),
      reconnect: vi.fn(),
    } as any);

    renderWithMinimalWrapper(<ConnectionStatusIndicator />);

    const indicator = screen.getByTestId('connection-indicator');
    fireEvent.mouseEnter(indicator);

    await waitFor(() => {
      expect(screen.getByText('Connection timeout')).toBeInTheDocument();
    });
  });
});
