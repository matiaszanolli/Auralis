/**
 * connectionSlice reducer unit tests (#2815)
 *
 * Covers all action creators, state transitions, and derived selectors.
 */

import reducer, {
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
  selectWSConnected,
  selectAPIConnected,
  selectLatency,
  selectReconnectAttempts,
  selectIsFullyConnected,
  selectCanReconnect,
  selectConnectionHealth,
} from '../connectionSlice';
import type { ConnectionState } from '../connectionSlice';

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

describe('connectionSlice', () => {
  it('should return initial state', () => {
    const state = reducer(undefined, { type: 'unknown' });
    expect(state.wsConnected).toBe(false);
    expect(state.apiConnected).toBe(false);
    expect(state.reconnectAttempts).toBe(0);
  });

  // ─── Connection status ────────────────────────────────────────

  it('setWSConnected(true) resets reconnect attempts and clears error', () => {
    let state: ConnectionState = {
      ...initialState,
      reconnectAttempts: 3,
      lastError: 'timeout',
    };
    state = reducer(state, setWSConnected(true));
    expect(state.wsConnected).toBe(true);
    expect(state.reconnectAttempts).toBe(0);
    expect(state.lastError).toBeNull();
    expect(state.lastUpdated).toBeGreaterThan(0);
  });

  it('setWSConnected(false) does not reset reconnect attempts', () => {
    let state: ConnectionState = { ...initialState, wsConnected: true, reconnectAttempts: 2 };
    state = reducer(state, setWSConnected(false));
    expect(state.wsConnected).toBe(false);
    expect(state.reconnectAttempts).toBe(2);
  });

  it('setAPIConnected(true) clears error', () => {
    let state: ConnectionState = { ...initialState, lastError: 'api down' };
    state = reducer(state, setAPIConnected(true));
    expect(state.apiConnected).toBe(true);
    expect(state.lastError).toBeNull();
  });

  it('setAPIConnected(false) preserves error', () => {
    let state: ConnectionState = { ...initialState, lastError: 'api down' };
    state = reducer(state, setAPIConnected(false));
    expect(state.apiConnected).toBe(false);
    expect(state.lastError).toBe('api down');
  });

  // ─── Latency ─────────────────────────────────────────────────

  it('setLatency updates latency', () => {
    const state = reducer(initialState, setLatency(150));
    expect(state.latency).toBe(150);
  });

  // ─── Reconnect attempts ──────────────────────────────────────

  it('incrementReconnectAttempts increments by 1', () => {
    const state = reducer(initialState, incrementReconnectAttempts());
    expect(state.reconnectAttempts).toBe(1);
    expect(state.lastReconnectTime).toBeGreaterThan(0);
  });

  it('incrementReconnectAttempts caps at maxReconnectAttempts', () => {
    let state: ConnectionState = { ...initialState, reconnectAttempts: 5 };
    state = reducer(state, incrementReconnectAttempts());
    expect(state.reconnectAttempts).toBe(5);
  });

  it('resetReconnectAttempts resets to zero', () => {
    let state: ConnectionState = { ...initialState, reconnectAttempts: 3 };
    state = reducer(state, resetReconnectAttempts());
    expect(state.reconnectAttempts).toBe(0);
  });

  it('setMaxReconnectAttempts updates max', () => {
    const state = reducer(initialState, setMaxReconnectAttempts(10));
    expect(state.maxReconnectAttempts).toBe(10);
  });

  // ─── Error ────────────────────────────────────────────────────

  it('setError sets error message', () => {
    const state = reducer(initialState, setError('connection lost'));
    expect(state.lastError).toBe('connection lost');
  });

  it('clearError clears error', () => {
    let state = reducer(initialState, setError('err'));
    state = reducer(state, clearError());
    expect(state.lastError).toBeNull();
  });

  // ─── Bulk update ──────────────────────────────────────────────

  it('updateConnectionState merges partial state', () => {
    const state = reducer(
      initialState,
      updateConnectionState({ wsConnected: true, latency: 42 })
    );
    expect(state.wsConnected).toBe(true);
    expect(state.latency).toBe(42);
    expect(state.apiConnected).toBe(false); // unchanged
  });

  // ─── Reset ────────────────────────────────────────────────────

  it('resetConnection returns to initial state', () => {
    let state = reducer(initialState, setWSConnected(true));
    state = reducer(state, setLatency(100));
    state = reducer(state, resetConnection());
    expect(state.wsConnected).toBe(false);
    expect(state.latency).toBe(0);
  });

  // ─── Selectors ────────────────────────────────────────────────

  it('basic selectors return correct values', () => {
    const state: ConnectionState = {
      ...initialState,
      wsConnected: true,
      apiConnected: true,
      latency: 50,
      reconnectAttempts: 2,
    };
    const root = { connection: state };

    expect(selectWSConnected(root)).toBe(true);
    expect(selectAPIConnected(root)).toBe(true);
    expect(selectLatency(root)).toBe(50);
    expect(selectReconnectAttempts(root)).toBe(2);
  });

  it('selectIsFullyConnected requires both connections', () => {
    expect(selectIsFullyConnected({ connection: { ...initialState, wsConnected: true, apiConnected: true } })).toBe(true);
    expect(selectIsFullyConnected({ connection: { ...initialState, wsConnected: true, apiConnected: false } })).toBe(false);
    expect(selectIsFullyConnected({ connection: { ...initialState, wsConnected: false, apiConnected: true } })).toBe(false);
  });

  it('selectCanReconnect checks attempts vs max', () => {
    expect(selectCanReconnect({ connection: { ...initialState, reconnectAttempts: 3 } })).toBe(true);
    expect(selectCanReconnect({ connection: { ...initialState, reconnectAttempts: 5 } })).toBe(false);
  });

  // ─── Connection health ────────────────────────────────────────

  it('selectConnectionHealth returns disconnected when not connected', () => {
    expect(selectConnectionHealth({ connection: initialState })).toBe('disconnected');
  });

  it('selectConnectionHealth returns good for low latency', () => {
    const state: ConnectionState = { ...initialState, wsConnected: true, apiConnected: true, latency: 50 };
    expect(selectConnectionHealth({ connection: state })).toBe('good');
  });

  it('selectConnectionHealth returns moderate for medium latency', () => {
    const state: ConnectionState = { ...initialState, wsConnected: true, apiConnected: true, latency: 300 };
    expect(selectConnectionHealth({ connection: state })).toBe('moderate');
  });

  it('selectConnectionHealth returns slow for high latency', () => {
    const state: ConnectionState = { ...initialState, wsConnected: true, apiConnected: true, latency: 600 };
    expect(selectConnectionHealth({ connection: state })).toBe('slow');
  });
});
