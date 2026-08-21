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
     *
     * No production dispatch sites (#4921) — kept as an idiomatic
     * Redux action. Live sync uses field-level dispatches; see the note on
     * resetPlayer in playerSlice.ts for why the bulk-update siblings were
     * deleted rather than documented.
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
     * Reset connection state
     *
     * No production dispatch sites (#4921) — kept as an idiomatic Redux reset. Live WebSocket sync
     * dispatches field-level actions from usePlayerStateSync.ts /
     * useAPIHealthPoll.ts, which is the intended architecture; the bulk
     * updatePlaybackState/updateStreamingInfo/updateConnectionState actions
     * that sat beside these were deleted in #4921 because they duplicated
     * hardening the field-level path already has.
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
