/**
 * EnhancementContext apiRequest Regression Test
 *
 * Regression test for issue #2653:
 * Verifies that API errors from the `post()` utility (apiRequest)
 * are properly surfaced through the EnhancementContext error state.
 *
 * NOTE: The global test setup (setup.ts) auto-mocks EnhancementContext.
 * We must vi.unmock it here to test the real implementation.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';
// Undo the global auto-mock from setup.ts so we test the REAL EnhancementContext
vi.unmock('../EnhancementContext');

// Mock apiRequest — the key migration from raw fetch (#2653)
const mockPost = vi.fn();
vi.mock('@/utils/apiRequest', () => ({
  post: (...args: any[]) => mockPost(...args),
}));

import { EnhancementProvider, useEnhancement } from '../EnhancementContext';

// Test component that exposes context values via a mutable ref
let contextValue: ReturnType<typeof useEnhancement>;
function TestConsumer() {
  contextValue = useEnhancement();
  return null;
}

function renderWithProvider() {
  return render(
    <EnhancementProvider>
      <TestConsumer />
    </EnhancementProvider>
  );
}

describe('EnhancementContext apiRequest migration (regression: #2653)', () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  it('uses post() from apiRequest, not raw fetch', async () => {
    mockPost.mockResolvedValue({ settings: { enabled: true } });
    renderWithProvider();

    await act(async () => {
      await (contextValue.setEnabled as any)(true);
    });

    expect(mockPost).toHaveBeenCalledTimes(1);
  });

  it('surfaces API errors through the error state', async () => {
    const apiError = new Error('Network failure');
    mockPost.mockRejectedValue(apiError);
    renderWithProvider();

    await act(async () => {
      try {
        await (contextValue.setPreset as any)('warm');
      } catch {
        // Expected to throw
      }
    });

    expect(contextValue.error).toBeTruthy();
    expect(contextValue.error?.message).toBe('Network failure');
  });

  it('clears error on next successful call', async () => {
    // First call fails
    mockPost.mockRejectedValueOnce(new Error('fail'));
    renderWithProvider();

    await act(async () => {
      try { await (contextValue.setEnabled as any)(true); } catch {}
    });
    expect(contextValue.error).toBeTruthy();

    // Second call succeeds
    mockPost.mockResolvedValueOnce({ settings: { intensity: 0.5 } });
    await act(async () => {
      await (contextValue.setIntensity as any)(0.5);
    });
    expect(contextValue.error).toBeNull();
  });

  it('isProcessing reflects in-flight state correctly', async () => {
    let resolvePost!: (v: any) => void;
    mockPost.mockReturnValue(new Promise(r => { resolvePost = r; }));
    renderWithProvider();

    expect(contextValue.isProcessing).toBe(false);

    let promise: Promise<any>;
    act(() => {
      promise = (contextValue.setEnabled as any)(true);
    });

    expect(contextValue.isProcessing).toBe(true);

    await act(async () => {
      resolvePost({ settings: { enabled: true } });
      await promise!;
    });

    expect(contextValue.isProcessing).toBe(false);
  });
});
