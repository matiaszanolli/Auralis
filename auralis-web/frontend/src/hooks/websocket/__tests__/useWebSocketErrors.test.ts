import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';

// Capture the subscription callback
let subscriptionCallback: ((message: any) => void) | undefined;

vi.mock('../useWebSocketSubscription', () => ({
  useWebSocketSubscription: vi.fn((_types: string[], callback: (msg: any) => void) => {
    subscriptionCallback = callback;
  }),
}));

const mockWarning = vi.fn();

vi.mock('@/components/shared/Toast', () => ({
  useToast: vi.fn(() => ({
    warning: mockWarning,
  })),
}));

import { useWebSocketErrors } from '../useWebSocketErrors';
import { useWebSocketSubscription } from '../useWebSocketSubscription';

describe('useWebSocketErrors', () => {
  beforeEach(() => {
    subscriptionCallback = undefined;
    mockWarning.mockClear();
    vi.mocked(useWebSocketSubscription).mockClear();
  });

  it('renders without error', () => {
    const { result } = renderHook(() => useWebSocketErrors());
    expect(result.current).toBeUndefined();
  });

  it('subscribes to error messages', () => {
    renderHook(() => useWebSocketErrors());
    expect(useWebSocketSubscription).toHaveBeenCalledWith(
      ['error'],
      expect.any(Function),
    );
  });

  it('calls warning with message when error has a message', () => {
    renderHook(() => useWebSocketErrors());
    expect(subscriptionCallback).toBeDefined();

    subscriptionCallback!({
      type: 'error',
      error: 'rate_limit_exceeded',
      message: 'Too many requests',
    });

    expect(mockWarning).toHaveBeenCalledWith('Too many requests');
  });

  it('calls warning with fallback text when error has no message', () => {
    renderHook(() => useWebSocketErrors());
    expect(subscriptionCallback).toBeDefined();

    subscriptionCallback!({
      type: 'error',
      error: 'unknown_error',
    });

    expect(mockWarning).toHaveBeenCalledWith('An error occurred');
  });
});
