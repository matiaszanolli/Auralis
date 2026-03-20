/**
 * useOptimisticUpdate Hook Tests
 *
 * Tests for optimistic UI updates with rollback on failure.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useOptimisticUpdate } from '../useOptimisticUpdate';

describe('useOptimisticUpdate', () => {
  let asyncOp: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    asyncOp = vi.fn();
  });

  describe('initial state', () => {
    it('returns the initial state value', () => {
      const { result } = renderHook(() =>
        useOptimisticUpdate('initial', asyncOp)
      );

      expect(result.current.state).toBe('initial');
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
    });
  });

  describe('successful update', () => {
    it('sets optimistic value immediately then replaces with server result', async () => {
      asyncOp.mockResolvedValueOnce('server-result');

      const { result } = renderHook(() =>
        useOptimisticUpdate('initial', asyncOp)
      );

      let executePromise: Promise<unknown>;
      act(() => {
        executePromise = result.current.execute('optimistic', 'arg1');
      });

      // Optimistic value applied synchronously
      expect(result.current.state).toBe('optimistic');
      expect(result.current.isLoading).toBe(true);

      await act(async () => {
        await executePromise;
      });

      expect(result.current.state).toBe('server-result');
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('passes args through to the async operation', async () => {
      asyncOp.mockResolvedValueOnce('ok');

      const { result } = renderHook(() =>
        useOptimisticUpdate('init', asyncOp)
      );

      await act(async () => {
        await result.current.execute('opt', 'a', 'b');
      });

      expect(asyncOp).toHaveBeenCalledWith('a', 'b');
    });

    it('calls onSuccess callback with the result', async () => {
      asyncOp.mockResolvedValueOnce(42);
      const onSuccess = vi.fn();

      const { result } = renderHook(() =>
        useOptimisticUpdate<number, []>(0, asyncOp, { onSuccess })
      );

      await act(async () => {
        await result.current.execute(10);
      });

      expect(onSuccess).toHaveBeenCalledWith(42);
    });
  });

  describe('rollback on failure', () => {
    it('rolls back to previous state on error', async () => {
      const error = new Error('Network error');
      asyncOp.mockRejectedValueOnce(error);

      const { result } = renderHook(() =>
        useOptimisticUpdate('original', asyncOp)
      );

      await act(async () => {
        try {
          await result.current.execute('optimistic');
        } catch {
          // expected
        }
      });

      expect(result.current.state).toBe('original');
      expect(result.current.error).toBe(error);
      expect(result.current.isLoading).toBe(false);
    });

    it('calls onError callback', async () => {
      const error = new Error('fail');
      asyncOp.mockRejectedValueOnce(error);
      const onError = vi.fn();

      const { result } = renderHook(() =>
        useOptimisticUpdate('init', asyncOp, { onError })
      );

      await act(async () => {
        try {
          await result.current.execute('opt');
        } catch {
          // expected
        }
      });

      expect(onError).toHaveBeenCalledWith(error);
    });

    it('rolls back to the state at execute-time, not initial state', async () => {
      asyncOp.mockResolvedValueOnce('second');

      const { result } = renderHook(() =>
        useOptimisticUpdate('first', asyncOp)
      );

      // First successful update
      await act(async () => {
        await result.current.execute('opt1');
      });

      expect(result.current.state).toBe('second');

      // Second update fails — should roll back to 'second', not 'first'
      asyncOp.mockRejectedValueOnce(new Error('fail'));

      await act(async () => {
        try {
          await result.current.execute('opt2');
        } catch {
          // expected
        }
      });

      expect(result.current.state).toBe('second');
    });
  });

  describe('reset', () => {
    it('resets to initial state', async () => {
      asyncOp.mockResolvedValueOnce('changed');

      const { result } = renderHook(() =>
        useOptimisticUpdate('initial', asyncOp)
      );

      await act(async () => {
        await result.current.execute('opt');
      });

      expect(result.current.state).toBe('changed');

      act(() => {
        result.current.reset();
      });

      expect(result.current.state).toBe('initial');
      expect(result.current.error).toBeNull();
      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('setState', () => {
    it('allows direct state manipulation', () => {
      const { result } = renderHook(() =>
        useOptimisticUpdate('initial', asyncOp)
      );

      act(() => {
        result.current.setState('direct');
      });

      expect(result.current.state).toBe('direct');
    });
  });

  describe('error clearing', () => {
    it('clears previous error on new execute', async () => {
      asyncOp.mockRejectedValueOnce(new Error('first fail'));

      const { result } = renderHook(() =>
        useOptimisticUpdate('init', asyncOp)
      );

      await act(async () => {
        try {
          await result.current.execute('opt');
        } catch {
          // expected
        }
      });

      expect(result.current.error).not.toBeNull();

      asyncOp.mockResolvedValueOnce('success');

      await act(async () => {
        await result.current.execute('opt2');
      });

      expect(result.current.error).toBeNull();
    });
  });
});
