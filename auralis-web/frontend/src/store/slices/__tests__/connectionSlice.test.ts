/**
 * connectionSlice reducer unit tests (#2815)
 *
 * Covers all action creators and state transitions.
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
  resetConnection,
} from '../connectionSlice';
import type { ConnectionState } from '../connectionSlice';
import { DEFAULT_MAX_RECONNECT_ATTEMPTS } from '@/config/timing';

const initialState: ConnectionState = {
  wsConnected: false,
  apiConnected: false,
  backendDegraded: false,
  latency: 0,
  reconnectAttempts: 0,
  maxReconnectAttempts: DEFAULT_MAX_RECONNECT_ATTEMPTS,
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

  // #6220: the slice's budget must equal the WebSocketManager default, or
  // canReconnect gives up before the manager does.
  it('initial reconnect budget equals the shared manager default (#6220)', () => {
    const state = reducer(undefined, { type: 'unknown' });
    expect(state.maxReconnectAttempts).toBe(DEFAULT_MAX_RECONNECT_ATTEMPTS);
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
    let state: ConnectionState = {
      ...initialState,
      reconnectAttempts: DEFAULT_MAX_RECONNECT_ATTEMPTS,
    };
    state = reducer(state, incrementReconnectAttempts());
    expect(state.reconnectAttempts).toBe(DEFAULT_MAX_RECONNECT_ATTEMPTS);
  });

  it('resetReconnectAttempts resets to zero', () => {
    let state: ConnectionState = { ...initialState, reconnectAttempts: 3 };
    state = reducer(state, resetReconnectAttempts());
    expect(state.reconnectAttempts).toBe(0);
  });

  it('setMaxReconnectAttempts updates max and bumps lastUpdated (#4458)', () => {
    const state = reducer(initialState, setMaxReconnectAttempts(10));
    expect(state.maxReconnectAttempts).toBe(10);
    expect(state.lastUpdated).toBeGreaterThan(0);
  });

  // ─── Error ────────────────────────────────────────────────────

  it('setError sets error message', () => {
    const state = reducer(initialState, setError('connection lost'));
    expect(state.lastError).toBe('connection lost');
  });

  it('clearError clears error and bumps lastUpdated (#4458)', () => {
    let state = reducer(initialState, setError('err'));
    state = reducer(state, clearError());
    expect(state.lastError).toBeNull();
    expect(state.lastUpdated).toBeGreaterThan(0);
  });

  // ─── Reset ────────────────────────────────────────────────────

  it('resetConnection returns to initial state', () => {
    let state = reducer(initialState, setWSConnected(true));
    state = reducer(state, setLatency(100));
    state = reducer(state, resetConnection());
    expect(state.wsConnected).toBe(false);
    expect(state.latency).toBe(0);
  });
});
