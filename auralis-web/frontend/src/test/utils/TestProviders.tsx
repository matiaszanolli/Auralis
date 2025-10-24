/**
 * TestProviders
 *
 * Wrapper component that provides all necessary context providers for testing.
 * Use this to wrap components/hooks that depend on React contexts.
 */

import React, { ReactNode } from 'react';
import { WebSocketProvider } from '../../contexts/WebSocketContext';

interface TestProvidersProps {
  children: ReactNode;
  wsUrl?: string;
  autoConnect?: boolean;
}

/**
 * Wraps children with all necessary providers for testing
 *
 * @param children - Components to wrap
 * @param wsUrl - WebSocket URL (defaults to test mock URL)
 * @param autoConnect - Whether to auto-connect WebSocket (default: false for tests)
 */
export const TestProviders: React.FC<TestProvidersProps> = ({
  children,
  wsUrl = 'ws://localhost:8765/ws',
  autoConnect = false
}) => {
  return (
    <WebSocketProvider url={wsUrl} autoConnect={autoConnect}>
      {children}
    </WebSocketProvider>
  );
};

/**
 * Minimal test wrapper without WebSocket connection
 * Use for tests that don't need WebSocket functionality
 */
export const MinimalTestProviders: React.FC<{ children: ReactNode }> = ({ children }) => {
  return (
    <WebSocketProvider url="ws://test/ws" autoConnect={false}>
      {children}
    </WebSocketProvider>
  );
};

export default TestProviders;
