/**
 * Connection Redux Selectors
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Split out of store/selectors/index.ts (#4316).
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { createSelector } from '@reduxjs/toolkit';
import type { RootState } from '@/store/index';

export const connectionSelectors = {
  selectWSConnected: (state: RootState) => state.connection.wsConnected,
  selectAPIConnected: (state: RootState) => state.connection.apiConnected,
  selectLatency: (state: RootState) => state.connection.latency,
  selectReconnectAttempts: (state: RootState) => state.connection.reconnectAttempts,
  selectConnectionError: (state: RootState) => state.connection.lastError,
};

export const selectConnectionStatus = createSelector(
  [
    (state: RootState) => state.connection.wsConnected,
    (state: RootState) => state.connection.apiConnected,
    (state: RootState) => state.connection.latency,
    (state: RootState) => state.connection.reconnectAttempts,
    (state: RootState) => state.connection.maxReconnectAttempts,
  ],
  (wsConnected, apiConnected, latency, reconnectAttempts, maxReconnectAttempts) => {
    let health: 'healthy' | 'degraded' | 'disconnected' = 'disconnected';
    if (wsConnected && apiConnected) {
      health = 'healthy';
    } else if (wsConnected || apiConnected) {
      health = 'degraded';
    }
    return {
      connected: wsConnected && apiConnected,
      wsConnected,
      apiConnected,
      latency,
      health,
      canReconnect: reconnectAttempts < maxReconnectAttempts,
    };
  }
);
