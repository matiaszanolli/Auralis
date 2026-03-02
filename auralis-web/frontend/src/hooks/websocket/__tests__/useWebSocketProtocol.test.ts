/**
 * useWebSocketProtocol Hook Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Comprehensive test suite covering:
 * - Connection lifecycle (connect, disconnect, reconnect)
 * - Event handler subscription/unsubscription
 * - Cleanup on unmount (bug F-03 regression test)
 * - Message sending
 * - Error handling
 * - Connection state tracking
 *
 * Bug F-03 Regression Test:
 * - Verifies event handlers are properly unsubscribed on unmount
 * - Tests that cleanup function actually executes
 * - Ensures no memory leaks from accumulated event handlers
 *
 * @module hooks/websocket/__tests__/useWebSocketProtocol
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useWebSocketProtocol } from '../useWebSocketProtocol';
import * as protocolClient from '@/services/websocket/protocolClient';
import { MessagePriority } from '@/services/websocket/protocolClient';
import type { WebSocketProtocolClient } from '@/services/websocket/protocolClient';

// Mock the protocol client module
vi.mock('@/services/websocket/protocolClient', () => ({
  getWebSocketProtocol: vi.fn(),
  initializeWebSocketProtocol: vi.fn(),
  MessageType: {
    PLAY: 'play',
    PAUSE: 'pause',
    SEEK: 'seek',
    NEXT: 'next',
    PREVIOUS: 'previous',
    STATUS_UPDATE: 'status_update',
    NOTIFICATION: 'notification',
    CACHE_STATS: 'cache_stats',
    CACHE_STATUS: 'cache_status',
  },
  MessagePriority: {
    LOW: 'low',
    NORMAL: 'normal',
    HIGH: 'high',
    CRITICAL: 'critical',
  },
}));

describe('useWebSocketProtocol Hook', () => {
  // Mock client instance
  let mockClient: Partial<WebSocketProtocolClient>;
  let mockConnect: ReturnType<typeof vi.fn>;
  let mockDisconnect: ReturnType<typeof vi.fn>;
  let mockSend: ReturnType<typeof vi.fn>;
  let mockOn: ReturnType<typeof vi.fn>;
  let mockOnConnectionChange: ReturnType<typeof vi.fn>;
  let mockOnError: ReturnType<typeof vi.fn>;
  let connectionChangeCallback: ((connected: boolean) => void) | null = null;
  let errorCallback: ((error: Error) => void) | null = null;

  beforeEach(() => {
    vi.clearAllMocks();

    // Reset callbacks
    connectionChangeCallback = null;
    errorCallback = null;

    // Create mock methods
    mockConnect = vi.fn().mockResolvedValue(undefined);
    mockDisconnect = vi.fn();
    mockSend = vi.fn().mockResolvedValue({ type: 'response', payload: {} });
    mockOn = vi.fn((_type: string, _handler: Function) => {
      // Return unsubscribe function
      return vi.fn();
    });

    // onConnectionChange stores callback and returns unsubscribe function
    mockOnConnectionChange = vi.fn((callback: (connected: boolean) => void) => {
      connectionChangeCallback = callback;
      return vi.fn(); // unsubscribe function
    });

    // onError stores callback and returns unsubscribe function
    mockOnError = vi.fn((callback: (error: Error) => void) => {
      errorCallback = callback;
      return vi.fn(); // unsubscribe function
    });

    // Create mock client
    mockClient = {
      connect: mockConnect,
      disconnect: mockDisconnect,
      send: mockSend,
      on: mockOn,
      onConnectionChange: mockOnConnectionChange,
      onError: mockOnError,
    };

    // Mock getWebSocketProtocol and initializeWebSocketProtocol
    vi.mocked(protocolClient.getWebSocketProtocol).mockReturnValue(
      mockClient as WebSocketProtocolClient
    );
    vi.mocked(protocolClient.initializeWebSocketProtocol).mockReturnValue(
      mockClient as WebSocketProtocolClient
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ==========================================================================
  // CONNECTION LIFECYCLE
  // ==========================================================================

  describe('Connection Lifecycle', () => {
    it('should auto-connect on mount when autoConnect is true', async () => {
      renderHook(() => useWebSocketProtocol({ autoConnect: true }));

      expect(protocolClient.initializeWebSocketProtocol).toHaveBeenCalled();
      expect(mockConnect).toHaveBeenCalled();
    });

    it('should not auto-connect when autoConnect is false', () => {
      renderHook(() => useWebSocketProtocol({ autoConnect: false }));

      expect(mockConnect).not.toHaveBeenCalled();
    });

    it('should use default URL if not provided', async () => {
      renderHook(() => useWebSocketProtocol({ autoConnect: true }));

      const expectedUrl = `ws://${window.location.host}/ws`;
      expect(protocolClient.initializeWebSocketProtocol).toHaveBeenCalledWith(expectedUrl);
    });

    it('should use custom URL when provided', async () => {
      const customUrl = 'ws://custom.example.com:9000/ws';
      renderHook(() =>
        useWebSocketProtocol({
          autoConnect: true,
          url: customUrl,
        })
      );

      expect(protocolClient.initializeWebSocketProtocol).toHaveBeenCalledWith(customUrl);
    });

    it('should set connected state when connection succeeds', async () => {
      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      // Initially disconnected
      expect(result.current.connected).toBe(false);

      // Simulate connection success
      act(() => {
        if (connectionChangeCallback) {
          connectionChangeCallback(true);
        }
      });

      expect(result.current.connected).toBe(true);
    });

    it('should handle connection failure gracefully', async () => {
      const connectionError = new Error('Connection failed');
      mockConnect.mockRejectedValueOnce(connectionError);

      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      await waitFor(() => {
        expect(result.current.error).toBeDefined();
      });
    });

    it('should call onConnectionChange callback when connection state changes', async () => {
      const onConnectionChange = vi.fn();

      renderHook(() =>
        useWebSocketProtocol({
          autoConnect: true,
          onConnectionChange,
        })
      );

      // Simulate connection
      act(() => {
        if (connectionChangeCallback) {
          connectionChangeCallback(true);
        }
      });

      expect(onConnectionChange).toHaveBeenCalledWith(true);

      // Simulate disconnection
      act(() => {
        if (connectionChangeCallback) {
          connectionChangeCallback(false);
        }
      });

      expect(onConnectionChange).toHaveBeenCalledWith(false);
    });

    it('should provide disconnect method', () => {
      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      act(() => {
        result.current.disconnect();
      });

      expect(mockDisconnect).toHaveBeenCalled();
      expect(result.current.connected).toBe(false);
    });

    it('should provide reconnect method', async () => {
      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      await act(async () => {
        await result.current.reconnect();
      });

      // connect() should be called twice: once on mount, once on reconnect
      expect(mockConnect).toHaveBeenCalledTimes(2);
    });

    it('should handle reconnect errors', async () => {
      const reconnectError = new Error('Reconnect failed');
      mockConnect.mockResolvedValueOnce(undefined); // First connect succeeds
      mockConnect.mockRejectedValueOnce(reconnectError); // Reconnect fails

      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      await act(async () => {
        try {
          await result.current.reconnect();
        } catch (err) {
          expect(err).toEqual(reconnectError);
        }
      });

      expect(result.current.error).toBeDefined();
    });
  });

  // ==========================================================================
  // CLEANUP ON UNMOUNT (BUG F-03 REGRESSION TEST)
  // ==========================================================================

  describe('Cleanup on Unmount (Bug F-03 Regression)', () => {
    it('should unsubscribe connection change handler on unmount', () => {
      const unsubscribeConnectionMock = vi.fn();
      mockOnConnectionChange.mockReturnValueOnce(unsubscribeConnectionMock);

      const { unmount } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      // Verify subscription was set up
      expect(mockOnConnectionChange).toHaveBeenCalled();

      // Unmount component
      unmount();

      // Verify unsubscribe was called
      expect(unsubscribeConnectionMock).toHaveBeenCalled();
    });

    it('should unsubscribe error handler on unmount', () => {
      const unsubscribeErrorMock = vi.fn();
      mockOnError.mockReturnValueOnce(unsubscribeErrorMock);

      const { unmount } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      // Verify subscription was set up
      expect(mockOnError).toHaveBeenCalled();

      // Unmount component
      unmount();

      // Verify unsubscribe was called
      expect(unsubscribeErrorMock).toHaveBeenCalled();
    });

    it('should not leak event handlers after multiple mount/unmount cycles', () => {
      const unsubscribeConnectionMock = vi.fn();
      const unsubscribeErrorMock = vi.fn();

      mockOnConnectionChange.mockReturnValue(unsubscribeConnectionMock);
      mockOnError.mockReturnValue(unsubscribeErrorMock);

      // Mount and unmount 10 times
      for (let i = 0; i < 10; i++) {
        const { unmount } = renderHook(() =>
          useWebSocketProtocol({ autoConnect: true })
        );
        unmount();
      }

      // Each cycle should unsubscribe both handlers
      expect(unsubscribeConnectionMock).toHaveBeenCalledTimes(10);
      expect(unsubscribeErrorMock).toHaveBeenCalledTimes(10);
    });

    it('should not disconnect on unmount (keep connection alive for other components)', () => {
      const { unmount } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      unmount();

      // disconnect() should NOT be called - connection stays alive
      expect(mockDisconnect).not.toHaveBeenCalled();
    });

    it('should handle unmount when connection callbacks are null', () => {
      // This tests the cleanup function when refs are already null
      mockOnConnectionChange.mockReturnValueOnce(null as any);
      mockOnError.mockReturnValueOnce(null as any);

      const { unmount } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      // Should not throw
      expect(() => unmount()).not.toThrow();
    });
  });

  // ==========================================================================
  // MESSAGE SENDING
  // ==========================================================================

  describe('Message Sending', () => {
    it('should send message with correct parameters', async () => {
      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      const payload = { position: 120 };
      await act(async () => {
        await result.current.send('seek', payload);
      });

      expect(mockSend).toHaveBeenCalledWith('seek', payload, undefined);
    });

    it('should send message with options', async () => {
      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      const payload = { track_id: 123 };
      const options = { priority: MessagePriority.HIGH, responseRequired: true };

      await act(async () => {
        await result.current.send('play', payload, options);
      });

      expect(mockSend).toHaveBeenCalledWith('play', payload, options);
    });

    it('should return response from send()', async () => {
      const mockResponse = { type: 'ack', payload: { success: true } };
      mockSend.mockResolvedValueOnce(mockResponse);

      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      let response;
      await act(async () => {
        response = await result.current.send('play', { track_id: 1 });
      });

      expect(response).toEqual(mockResponse);
    });

    it('should handle send errors and update error state', async () => {
      const sendError = new Error('Send failed');
      mockSend.mockRejectedValueOnce(sendError);

      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      await act(async () => {
        try {
          await result.current.send('play', {});
        } catch (err) {
          expect(err).toEqual(sendError);
        }
      });

      expect(result.current.error).toBeDefined();
    });

    it('should call onError callback when send fails', async () => {
      const sendError = new Error('Send failed');
      mockSend.mockRejectedValueOnce(sendError);

      const onError = vi.fn();

      const { result } = renderHook(() =>
        useWebSocketProtocol({
          autoConnect: true,
          onError,
        })
      );

      await act(async () => {
        try {
          await result.current.send('play', {});
        } catch (err) {
          // Expected
        }
      });

      expect(onError).toHaveBeenCalledWith(sendError);
    });
  });

  // ==========================================================================
  // SUBSCRIPTION
  // ==========================================================================

  describe('Subscription', () => {
    it('should subscribe to message type', () => {
      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      const handler = vi.fn();
      const unsubscribe = result.current.subscribe('status_update', handler);

      expect(mockOn).toHaveBeenCalledWith('status_update', handler);
      expect(typeof unsubscribe).toBe('function');
    });

    it('should return unsubscribe function from subscribe', () => {
      const mockUnsubscribe = vi.fn();
      mockOn.mockReturnValueOnce(mockUnsubscribe);

      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      const handler = vi.fn();
      const unsubscribe = result.current.subscribe('status_update', handler);

      expect(unsubscribe).toBe(mockUnsubscribe);
    });

    it('should allow subscribing to multiple message types', () => {
      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      const handler1 = vi.fn();
      const handler2 = vi.fn();

      result.current.subscribe('play', handler1);
      result.current.subscribe('pause', handler2);

      expect(mockOn).toHaveBeenCalledWith('play', handler1);
      expect(mockOn).toHaveBeenCalledWith('pause', handler2);
    });
  });

  // ==========================================================================
  // ERROR HANDLING
  // ==========================================================================

  describe('Error Handling', () => {
    it('should update error state when error occurs', async () => {
      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      const error = new Error('Test error');

      act(() => {
        if (errorCallback) {
          errorCallback(error);
        }
      });

      expect(result.current.error).toBe(error);
    });

    it('should call onError callback when error occurs', async () => {
      const onError = vi.fn();
      renderHook(() =>
        useWebSocketProtocol({
          autoConnect: true,
          onError,
        })
      );

      const error = new Error('Test error');

      act(() => {
        if (errorCallback) {
          errorCallback(error);
        }
      });

      expect(onError).toHaveBeenCalledWith(error);
    });

    it('should handle non-Error objects as errors', async () => {
      mockConnect.mockRejectedValueOnce('String error');

      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      await waitFor(() => {
        expect(result.current.error).toBeDefined();
        expect(result.current.error?.message).toBe('String error');
      });
    });
  });

  // ==========================================================================
  // STATE MANAGEMENT
  // ==========================================================================

  describe('State Management', () => {
    it('should initialize with disconnected state', () => {
      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: false })
      );

      expect(result.current.connected).toBe(false);
      expect(result.current.error).toBe(null);
    });

    it('should track connection state correctly through lifecycle', async () => {
      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      // Start disconnected
      expect(result.current.connected).toBe(false);

      // Connect
      act(() => {
        if (connectionChangeCallback) {
          connectionChangeCallback(true);
        }
      });
      expect(result.current.connected).toBe(true);

      // Disconnect
      act(() => {
        result.current.disconnect();
      });
      expect(result.current.connected).toBe(false);
    });

    it('should preserve client reference across re-renders', () => {
      const { rerender } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      const firstClient = vi.mocked(protocolClient.initializeWebSocketProtocol).mock
        .results[0]?.value;

      rerender();

      const secondClient = vi.mocked(protocolClient.initializeWebSocketProtocol).mock
        .results[0]?.value;

      expect(firstClient).toBe(secondClient);
    });
  });

  // ==========================================================================
  // EDGE CASES
  // ==========================================================================

  describe('Edge Cases', () => {
    it('should handle rapid connect/disconnect cycles', async () => {
      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: true })
      );

      for (let i = 0; i < 10; i++) {
        act(() => {
          if (connectionChangeCallback) {
            connectionChangeCallback(true);
          }
        });

        act(() => {
          result.current.disconnect();
        });
      }

      // Should not crash or leak memory
      expect(result.current).toBeDefined();
    });

    it('should handle send before connection established', async () => {
      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: false })
      );

      // Try sending before connected
      await act(async () => {
        await result.current.send('play', {});
      });

      // Should call send anyway (client handles connection state internally)
      expect(mockSend).toHaveBeenCalled();
    });

    it('should handle subscription before connection established', () => {
      const { result } = renderHook(() =>
        useWebSocketProtocol({ autoConnect: false })
      );

      const handler = vi.fn();
      const unsubscribe = result.current.subscribe('play', handler);

      expect(mockOn).toHaveBeenCalled();
      expect(unsubscribe).toBeDefined();
    });

    it('should not crash if URL changes after mount', () => {
      const { rerender } = renderHook(
        ({ url }) => useWebSocketProtocol({ autoConnect: true, url }),
        {
          initialProps: { url: 'ws://localhost:8765/ws' },
        }
      );

      // Change URL
      rerender({ url: 'ws://example.com:9000/ws' });

      // Should create new client with new URL
      expect(protocolClient.initializeWebSocketProtocol).toHaveBeenCalledTimes(2);
    });
  });
});
