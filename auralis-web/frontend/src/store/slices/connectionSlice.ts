/**
 * Connection State Slice
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Redux slice for managing connection state including:
 * - WebSocket connection status
 * - API connection status
 * - Network latency
 * - Reconnection attempts
 *
 * Phase C.3: Component Testing & Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface ConnectionState {
  wsConnected: boolean;
  apiConnected: boolean;
  latency: number;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  lastError: string | null;
  lastReconnectTime: number;
  lastUpdated: number;
}

const initialState: ConnectionState = {
  wsConnected: false,
  apiConnected: false,
  latency: 0,
  reconnectAttempts: 0,
  maxReconnectAttempts: 5,
  lastError: null,
  lastReconnectTime: 0,
  lastUpdated: 0,
};

const connectionSlice = createSlice({
  name: 'connection',
  initialState,
  reducers: {
    /**
     * Set WebSocket connection status
     */
    setWSConnected(state, action: PayloadAction<boolean>) {
      state.wsConnected = action.payload;
      if (action.payload) {
        // Connected: reset reconnect attempts
        state.reconnectAttempts = 0;
        state.lastError = null;
      }
      state.lastUpdated = Date.now();
    },

    /**
     * Set API connection status
     */
    setAPIConnected(state, action: PayloadAction<boolean>) {
      state.apiConnected = action.payload;
      if (action.payload) {
        state.lastError = null;
      }
      state.lastUpdated = Date.now();
    },

    /**
     * Set network latency
     */
    setLatency(state, action: PayloadAction<number>) {
      state.latency = action.payload;
      state.lastUpdated = Date.now();
    },

    /**
     * Increment reconnect attempts
     */
    incrementReconnectAttempts(state) {
      state.reconnectAttempts = Math.min(
        state.reconnectAttempts + 1,
        state.maxReconnectAttempts
      );
      state.lastReconnectTime = Date.now();
      state.lastUpdated = Date.now();
    },

    /**
     * Reset reconnect attempts
     */
    resetReconnectAttempts(state) {
      state.reconnectAttempts = 0;
      state.lastUpdated = Date.now();
    },

    /**
     * Set max reconnect attempts
     */
    setMaxReconnectAttempts(state, action: PayloadAction<number>) {
      state.maxReconnectAttempts = action.payload;
    },

    /**
     * Set error message
     */
    setError(state, action: PayloadAction<string | null>) {
      state.lastError = action.payload;
      state.lastUpdated = Date.now();
    },

    /**
     * Clear error
     */
    clearError(state) {
      state.lastError = null;
    },

    /**
     * Update entire connection state
     */
    updateConnectionState(
      state,
      action: PayloadAction<Partial<Omit<ConnectionState, 'lastUpdated'>>>
    ) {
      Object.assign(state, action.payload);
      state.lastUpdated = Date.now();
    },

    /**
     * Reset connection state
     */
    resetConnection(state) {
      Object.assign(state, initialState);
    },
  },
});

export const {
  setWSConnected,
  setAPIConnected,
  setLatency,
  incrementReconnectAttempts,
  resetReconnectAttempts,
  setMaxReconnectAttempts,
  setError,
  clearError,
  updateConnectionState,
  resetConnection,
} = connectionSlice.actions;

// Selectors
export const selectWSConnected = (state: { connection: ConnectionState }) =>
  state.connection.wsConnected;
export const selectAPIConnected = (state: { connection: ConnectionState }) =>
  state.connection.apiConnected;
export const selectLatency = (state: { connection: ConnectionState }) =>
  state.connection.latency;
export const selectReconnectAttempts = (state: { connection: ConnectionState }) =>
  state.connection.reconnectAttempts;
export const selectMaxReconnectAttempts = (state: { connection: ConnectionState }) =>
  state.connection.maxReconnectAttempts;
export const selectLastError = (state: { connection: ConnectionState }) =>
  state.connection.lastError;
export const selectLastReconnectTime = (state: { connection: ConnectionState }) =>
  state.connection.lastReconnectTime;
export const selectConnectionState = (state: { connection: ConnectionState }) =>
  state.connection;

/**
 * Select if fully connected (both WebSocket and API)
 */
export const selectIsFullyConnected = (state: { connection: ConnectionState }) =>
  state.connection.wsConnected && state.connection.apiConnected;

/**
 * Select if can attempt reconnection
 */
export const selectCanReconnect = (state: { connection: ConnectionState }) =>
  state.connection.reconnectAttempts < state.connection.maxReconnectAttempts;

/**
 * Select connection health status
 */
export const selectConnectionHealth = (state: { connection: ConnectionState }) => {
  const { wsConnected, apiConnected, latency } = state.connection;

  if (!wsConnected || !apiConnected) {
    return 'disconnected';
  }

  if (latency > 500) {
    return 'slow';
  }

  if (latency > 200) {
    return 'moderate';
  }

  return 'good';
};

export default connectionSlice.reducer;
