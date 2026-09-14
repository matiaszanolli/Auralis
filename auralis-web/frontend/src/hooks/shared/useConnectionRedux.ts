/**
 * Connection Redux Hooks
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Connection-slice state and action hooks. Split out of useReduxState.ts
 * (#5239), which re-exports everything here.
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { useSelector, useDispatch, shallowEqual } from 'react-redux';
import { useCallback, useMemo } from 'react';
import type { RootState, AppDispatch } from '@/store';
import * as connectionActions from '@/store/slices/connectionSlice';

/**
 * Access entire connection state
 */
export const useConnectionState = () => {
  return useSelector((state: RootState) => state.connection, shallowEqual);
};

/**
 * Access connection status and management
 */
export const useConnection = () => {
  const dispatch = useDispatch<AppDispatch>();
  const state = useSelector((state: RootState) => state.connection, shallowEqual);

  const setWSConnected = useCallback(
    (connected: boolean) => dispatch(connectionActions.setWSConnected(connected)),
    [dispatch]
  );
  const setAPIConnected = useCallback(
    (connected: boolean) => dispatch(connectionActions.setAPIConnected(connected)),
    [dispatch]
  );
  const setLatency = useCallback(
    (latency: number) => dispatch(connectionActions.setLatency(latency)),
    [dispatch]
  );
  const incrementReconnectAttempts = useCallback(
    () => dispatch(connectionActions.incrementReconnectAttempts()),
    [dispatch]
  );
  const resetReconnectAttempts = useCallback(
    () => dispatch(connectionActions.resetReconnectAttempts()),
    [dispatch]
  );
  const clearError = useCallback(
    () => dispatch(connectionActions.clearError()),
    [dispatch]
  );

  // #3619: stable object identity (matches usePlayer pattern).
  return useMemo(
    () => ({
      wsConnected: state.wsConnected,
      apiConnected: state.apiConnected,
      latency: state.latency,
      reconnectAttempts: state.reconnectAttempts,
      maxReconnectAttempts: state.maxReconnectAttempts,
      lastError: state.lastError,
      isFullyConnected: state.wsConnected && state.apiConnected,
      canReconnect: state.reconnectAttempts < state.maxReconnectAttempts,
      connectionHealth: (state.wsConnected && state.apiConnected
        ? 'healthy'
        : state.wsConnected || state.apiConnected
          ? 'degraded'
          : 'disconnected') as 'healthy' | 'degraded' | 'disconnected',
      setWSConnected,
      setAPIConnected,
      setLatency,
      incrementReconnectAttempts,
      resetReconnectAttempts,
      clearError,
    }),
    [
      state.wsConnected,
      state.apiConnected,
      state.latency,
      state.reconnectAttempts,
      state.maxReconnectAttempts,
      state.lastError,
      setWSConnected,
      setAPIConnected,
      setLatency,
      incrementReconnectAttempts,
      resetReconnectAttempts,
      clearError,
    ]
  );
};

/**
 * Check connection status with health information
 */
export const useConnectionHealth = () => {
  const connection = useConnectionState();

  return {
    connected: connection.wsConnected && connection.apiConnected,
    wsConnected: connection.wsConnected,
    apiConnected: connection.apiConnected,
    latency: connection.latency,
    attempting: connection.reconnectAttempts > 0 && connection.reconnectAttempts < connection.maxReconnectAttempts,
    failed: connection.reconnectAttempts >= connection.maxReconnectAttempts,
    health:
      connection.wsConnected && connection.apiConnected
        ? 'connected'
        : connection.wsConnected || connection.apiConnected
          ? 'partial'
          : 'disconnected',
  };
};
