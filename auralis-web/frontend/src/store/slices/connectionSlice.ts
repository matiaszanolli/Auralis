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
    setWSConnected: {
      reducer(state, action: PayloadAction<boolean, string, { timestamp: number }>) {
        state.wsConnected = action.payload;
        if (action.payload) {
          // Connected: reset reconnect attempts
          state.reconnectAttempts = 0;
          state.lastError = null;
        }
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(isConnected: boolean) {
        return { payload: isConnected, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set API connection status
     */
    setAPIConnected: {
      reducer(state, action: PayloadAction<boolean, string, { timestamp: number }>) {
        state.apiConnected = action.payload;
        if (action.payload) {
          state.lastError = null;
        }
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(isConnected: boolean) {
        return { payload: isConnected, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Set network latency
     */
    setLatency: {
      reducer(state, action: PayloadAction<number, string, { timestamp: number }>) {
        state.latency = action.payload;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(latency: number) {
        return { payload: latency, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Increment reconnect attempts
     */
    incrementReconnectAttempts: {
      reducer(state, action: PayloadAction<void, string, { timestamp: number }>) {
        state.reconnectAttempts = Math.min(
          state.reconnectAttempts + 1,
          state.maxReconnectAttempts
        );
        state.lastReconnectTime = action.meta.timestamp;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare() {
        return { payload: undefined, meta: { timestamp: Date.now() } };
      },
    },

    /**
     * Reset reconnect attempts
     */
    resetReconnectAttempts: {
      reducer(state, action: PayloadAction<void, string, { timestamp: number }>) {
        state.reconnectAttempts = 0;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare() {
        return { payload: undefined, meta: { timestamp: Date.now() } };
      },
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
    setError: {
      reducer(state, action: PayloadAction<string | null, string, { timestamp: number }>) {
        state.lastError = action.payload;
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(error: string | null) {
        return { payload: error, meta: { timestamp: Date.now() } };
      },
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
    updateConnectionState: {
      reducer(
        state,
        action: PayloadAction<
          Partial<Omit<ConnectionState, 'lastUpdated'>>,
          string,
          { timestamp: number }
        >
      ) {
        Object.assign(state, action.payload);
        state.lastUpdated = action.meta.timestamp;
      },
      prepare(connectionState: Partial<Omit<ConnectionState, 'lastUpdated'>>) {
        return { payload: connectionState, meta: { timestamp: Date.now() } };
      },
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
