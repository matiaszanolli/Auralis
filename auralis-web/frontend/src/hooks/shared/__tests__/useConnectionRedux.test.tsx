/**
 * Direct spec for useConnectionState, the one shared Redux hook that remains (#6046).
 */
import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { Provider } from 'react-redux';
import type { ReactNode } from 'react';
import { createTestStore } from '@/test/test-utils';
import { useConnectionState } from '../useConnectionRedux';

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
