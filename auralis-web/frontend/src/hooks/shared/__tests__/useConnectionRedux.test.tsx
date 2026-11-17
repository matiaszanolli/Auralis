/**
 * Direct spec for useConnectionRedux (#5683): imports the module itself, not the useReduxState barrel.
 */
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import type { ReactNode } from 'react';
import { createTestStore } from '@/test/test-utils';
import { useConnection, useConnectionHealth, useConnectionState } from '../useConnectionRedux';

function setup(connection?: Record<string, unknown>) {
  const store = createTestStore(connection ? { connection: connection as never } : undefined);
  const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
  return { store, wrapper };
}

describe('useConnectionState', () => {
  it('reads the connection slice', () => {
    const { wrapper } = setup({ latency: 12 });
    const { result } = renderHook(() => useConnectionState(), { wrapper });
    expect(result.current.latency).toBe(12);
  });
});

describe('useConnection', () => {
  it.each([
    [true, true, 'healthy'],
    [true, false, 'degraded'],
    [false, true, 'degraded'],
    [false, false, 'disconnected'],
  ])('ws=%s api=%s derives connectionHealth %s', (ws, api, health) => {
    const { wrapper } = setup({ wsConnected: ws, apiConnected: api });
    const { result } = renderHook(() => useConnection(), { wrapper });

    expect(result.current.connectionHealth).toBe(health);
    expect(result.current.isFullyConnected).toBe(ws && api);
  });

  it('canReconnect flips off once the attempts reach the maximum', () => {
    const { store, wrapper } = setup({ reconnectAttempts: 0, maxReconnectAttempts: 2 });
    const { result } = renderHook(() => useConnection(), { wrapper });
    expect(result.current.canReconnect).toBe(true);

    act(() => { result.current.incrementReconnectAttempts(); });
    act(() => { result.current.incrementReconnectAttempts(); });
    expect(store.getState().connection.reconnectAttempts).toBe(2);
    expect(result.current.canReconnect).toBe(false);

    act(() => { result.current.resetReconnectAttempts(); });
    expect(result.current.canReconnect).toBe(true);
  });

  it('setters dispatch to the slice', () => {
    const { store, wrapper } = setup();
    const { result } = renderHook(() => useConnection(), { wrapper });

    act(() => {
      result.current.setWSConnected(true);
      result.current.setAPIConnected(true);
      result.current.setLatency(33);
    });
    const { connection } = store.getState();
    expect(connection.wsConnected).toBe(true);
    expect(connection.apiConnected).toBe(true);
    expect(connection.latency).toBe(33);
  });
});

describe('useConnectionHealth', () => {
  it('reports connected only when both channels are up', () => {
    const { wrapper } = setup({ wsConnected: true, apiConnected: true });
    const { result } = renderHook(() => useConnectionHealth(), { wrapper });
    expect(result.current).toMatchObject({ connected: true, health: 'connected', failed: false, attempting: false });
  });

  it('reports partial when one channel is up', () => {
    const { wrapper } = setup({ wsConnected: true, apiConnected: false });
    const { result } = renderHook(() => useConnectionHealth(), { wrapper });
    expect(result.current).toMatchObject({ connected: false, health: 'partial' });
  });

  it('is attempting between the first retry and the maximum, then failed', () => {
    const mid = setup({ reconnectAttempts: 1, maxReconnectAttempts: 3 });
    expect(renderHook(() => useConnectionHealth(), { wrapper: mid.wrapper }).result.current)
      .toMatchObject({ attempting: true, failed: false });

    const done = setup({ reconnectAttempts: 3, maxReconnectAttempts: 3 });
    expect(renderHook(() => useConnectionHealth(), { wrapper: done.wrapper }).result.current)
      .toMatchObject({ attempting: false, failed: true });
  });
});
