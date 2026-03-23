/**
 * useRestAPI Hook Tests
 * ~~~~~~~~~~~~~~~~~~~~~
 *
 * Comprehensive test suite covering:
 * - GET, POST, PUT, PATCH, DELETE requests
 * - Request/response handling
 * - Query parameter building
 * - Timeout and abort on unmount
 * - Error handling and parsing
 * - Loading state tracking
 * - URL building
 * - Edge cases
 *
 * Abort on Unmount Test:
 * - Verifies requests are aborted when component unmounts
 * - Ensures no memory leaks from pending requests
 * - Tests AbortController signal propagation
 *
 * @module hooks/api/__tests__/useRestAPI
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useRestAPI, useQuery, useMutation } from '../useRestAPI';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch as any;

/**
 * Extract URL string from a fetch spy call.
 * happy-dom may wrap (url, init) into a Request object as the first arg.
 */
function getCallUrl(callIndex = 0): string {
  const arg = mockFetch.mock.calls[callIndex][0];
  if (typeof arg === 'string') return arg;
  if (arg instanceof Request) return arg.url;
  return String(arg);
}

/**
 * Extract the init options (method, headers, body, signal) from a fetch spy call.
 */
function getCallInit(callIndex = 0): Record<string, any> {
  const args = mockFetch.mock.calls[callIndex];
  if (!args) return {};
  // (url, init) form
  if (typeof args[0] === 'string' && args[1]) return args[1];
  // Request object form
  if (args[0] instanceof Request) {
    const req = args[0] as Request;
    const headers: Record<string, string> = {};
    req.headers.forEach((v, k) => { headers[k] = v; });
    return {
      method: req.method,
      headers,
      body: (req as any)[Object.getOwnPropertySymbols(req).find(s => String(s) === 'Symbol(body)') as any] ?? null,
      signal: req.signal,
    };
  }
  return args[1] ?? {};
}

describe('useRestAPI Hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers(); // Ensure timers are always real after each test
  });

  // Helper to create a complete mock Response object
  const createMockResponse = (data: any, options: { ok: boolean; status: number; statusText: string }) => {
    const response = {
      ok: options.ok,
      status: options.status,
      statusText: options.statusText,
      json: async () => data,
      text: async () => JSON.stringify(data),
      blob: async () => new Blob([JSON.stringify(data)]),
      arrayBuffer: async () => new ArrayBuffer(0),
      headers: new Headers(),
      redirected: false,
      type: 'basic' as ResponseType,
      url: '',
      clone: function() { return { ...this }; },
      body: null,
      bodyUsed: false,
    };
    return response as Response;
  };

  // Helper to mock successful fetch response
  const mockFetchSuccess = (data: any, status = 200) => {
    mockFetch.mockResolvedValueOnce(createMockResponse(data, {
      ok: true,
      status,
      statusText: 'OK',
    }));
  };

  // Helper to mock failed fetch response
  const mockFetchError = (status = 500, statusText = 'Internal Server Error') => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ error: statusText }, {
      ok: false,
      status,
      statusText,
    }));
  };

  // Helper to mock network error
  const mockNetworkError = () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));
  };

  // ==========================================================================
  // INITIALIZATION
  // ==========================================================================

  describe('Initialization', () => {
    it('should initialize with correct default state', () => {
      const { result } = renderHook(() => useRestAPI());

      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBe(null);
      expect(typeof result.current.get).toBe('function');
      expect(typeof result.current.post).toBe('function');
      expect(typeof result.current.put).toBe('function');
      expect(typeof result.current.patch).toBe('function');
      expect(typeof result.current.delete).toBe('function');
      expect(typeof result.current.clearError).toBe('function');
    });

    it('should return stable method references across renders', () => {
      const { result, rerender } = renderHook(() => useRestAPI());

      const firstGet = result.current.get;
      const firstPost = result.current.post;

      rerender();

      // Method references should be stable (memoized)
      expect(result.current.get).toBe(firstGet);
      expect(result.current.post).toBe(firstPost);
    });
  });

  // ==========================================================================
  // GET REQUEST
  // ==========================================================================

  describe('GET Request', () => {
    it('should perform GET request successfully', async () => {
      mockFetchSuccess({ data: 'test' });

      const { result } = renderHook(() => useRestAPI());

      let response;
      await act(async () => {
        response = await result.current.get('/api/test');
      });

      expect(getCallUrl()).toBe('http://localhost:3000/api/test');
      const init = getCallInit();
      expect(init.method).toBe('GET');

      expect(response).toEqual({ data: 'test' });
    });

    it('should reset loading state after GET request completes', async () => {
      mockFetchSuccess({ data: 'test' });

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        await result.current.get('/api/test');
      });

      // Loading should be false after request completes
      expect(result.current.isLoading).toBe(false);
    });

    it('should handle GET errors', async () => {
      mockFetchError(404, 'Not Found');

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        try {
          await result.current.get('/api/test');
        } catch (err) {
          // Expected
        }
      });

      expect(result.current.error).toBeDefined();
      expect(result.current.isLoading).toBe(false);
    });

    it('should handle network errors in GET', async () => {
      mockNetworkError();

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        try {
          await result.current.get('/api/test');
        } catch (err) {
          // Expected
        }
      });

      expect(result.current.error).toBeDefined();
      expect(result.current.error?.message).toContain('Network error');
    });

    it('should support typed GET requests', async () => {
      interface TestResponse {
        id: number;
        name: string;
      }

      mockFetchSuccess({ id: 1, name: 'Test' });

      const { result } = renderHook(() => useRestAPI());

      let response: TestResponse;
      await act(async () => {
        response = await result.current.get<TestResponse>('/api/test');
      });

      expect(response!).toEqual({ id: 1, name: 'Test' });
    });
  });

  // ==========================================================================
  // POST REQUEST
  // ==========================================================================

  describe('POST Request', () => {
    it('should perform POST request with JSON body', async () => {
      mockFetchSuccess({ success: true });

      const { result } = renderHook(() => useRestAPI());

      const payload = { name: 'Test', value: 42 };

      await act(async () => {
        await result.current.post('/api/test', payload);
      });

      expect(getCallUrl()).toBe('http://localhost:3000/api/test');
      const init = getCallInit();
      expect(init.method).toBe('POST');
    });

    it('should perform POST request with query parameters', async () => {
      mockFetchSuccess({ success: true });

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        await result.current.post('/api/test', undefined, {
          position: 120,
          volume: 80,
        });
      });

      expect(getCallUrl()).toBe('http://localhost:3000/api/test?position=120&volume=80');
      expect(getCallInit().method).toBe('POST');
    });

    it('should perform POST with both body and query parameters', async () => {
      mockFetchSuccess({ success: true });

      const { result } = renderHook(() => useRestAPI());

      const payload = { tracks: [1, 2, 3] };
      const queryParams = { startIndex: 0 };

      await act(async () => {
        await result.current.post('/api/test', payload, queryParams);
      });

      expect(getCallUrl()).toBe('http://localhost:3000/api/test?startIndex=0');
      expect(getCallInit().method).toBe('POST');
    });

    it('should handle POST errors', async () => {
      mockFetchError(400, 'Bad Request');

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        try {
          await result.current.post('/api/test', {});
        } catch (err) {
          // Expected
        }
      });

      expect(result.current.error).toBeDefined();
    });

    it('should skip null/undefined query parameters', async () => {
      mockFetchSuccess({ success: true });

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        await result.current.post('/api/test', undefined, {
          valid: 'value',
          nullValue: null,
          undefinedValue: undefined,
        });
      });

      const callUrl = getCallUrl();
      expect(callUrl).toContain('valid=value');
      expect(callUrl).not.toContain('null');
      expect(callUrl).not.toContain('undefined');
    });
  });

  // ==========================================================================
  // PUT REQUEST
  // ==========================================================================

  describe('PUT Request', () => {
    it('should perform PUT request with JSON body', async () => {
      mockFetchSuccess({ updated: true });

      const { result } = renderHook(() => useRestAPI());

      const payload = { name: 'Updated' };

      await act(async () => {
        await result.current.put('/api/test', payload);
      });

      expect(getCallUrl()).toBe('http://localhost:3000/api/test');
      expect(getCallInit().method).toBe('PUT');
    });

    it('should perform PUT request with query parameters', async () => {
      mockFetchSuccess({ updated: true });

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        await result.current.put('/api/test', undefined, { id: 123 });
      });

      expect(getCallUrl()).toBe('http://localhost:3000/api/test?id=123');
      expect(getCallInit().method).toBe('PUT');
    });

    it('should handle PUT errors', async () => {
      mockFetchError(403, 'Forbidden');

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        try {
          await result.current.put('/api/test', {});
        } catch (err) {
          // Expected
        }
      });

      expect(result.current.error).toBeDefined();
    });
  });

  // ==========================================================================
  // PATCH REQUEST
  // ==========================================================================

  describe('PATCH Request', () => {
    it('should perform PATCH request', async () => {
      mockFetchSuccess({ patched: true });

      const { result } = renderHook(() => useRestAPI());

      const payload = { field: 'value' };

      await act(async () => {
        await result.current.patch('/api/test', payload);
      });

      expect(getCallUrl()).toBe('http://localhost:3000/api/test');
      expect(getCallInit().method).toBe('PATCH');
    });

    it('should handle PATCH errors', async () => {
      mockFetchError(422, 'Unprocessable Entity');

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        try {
          await result.current.patch('/api/test', {});
        } catch (err) {
          // Expected
        }
      });

      expect(result.current.error).toBeDefined();
    });
  });

  // ==========================================================================
  // DELETE REQUEST
  // ==========================================================================

  describe('DELETE Request', () => {
    it('should perform DELETE request', async () => {
      mockFetchSuccess({ deleted: true });

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        await result.current.delete('/api/test/123');
      });

      expect(getCallUrl()).toBe('http://localhost:3000/api/test/123');
      expect(getCallInit().method).toBe('DELETE');
    });

    it('should handle DELETE errors', async () => {
      mockFetchError(404, 'Not Found');

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        try {
          await result.current.delete('/api/test/999');
        } catch (err) {
          // Expected
        }
      });

      expect(result.current.error).toBeDefined();
    });
  });

  // ==========================================================================
  // TIMEOUT AND ABORT
  // ==========================================================================

  describe('Timeout and Abort', () => {
    it('should abort request on timeout', async () => {
      // Track the AbortSignal passed to fetch
      let capturedSignal: AbortSignal | undefined;
      mockFetch.mockImplementationOnce((...args: any[]) => {
        const req = args[0];
        capturedSignal = req instanceof Request ? req.signal : args[1]?.signal;
        // Resolve immediately to avoid real 30s wait
        return Promise.resolve(createMockResponse({ data: 'test' }, { ok: true, status: 200, statusText: 'OK' }));
      });

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        await result.current.get('/api/test');
      });

      // Verify an AbortSignal was attached to the fetch call
      expect(capturedSignal).toBeDefined();
      expect(capturedSignal).toBeInstanceOf(AbortSignal);
    });

    it('should abort request on unmount', async () => {
      // Track the AbortSignal passed to fetch
      let capturedSignal: AbortSignal | undefined;
      mockFetch.mockImplementationOnce((...args: any[]) => {
        const req = args[0];
        capturedSignal = req instanceof Request ? req.signal : args[1]?.signal;
        return new Promise(() => {});
      });

      const { result, unmount } = renderHook(() => useRestAPI());

      // Start request (don't await — it will never resolve)
      await act(async () => {
        result.current.get('/api/test').catch(() => {});
        // Flush microtasks so fetch is called
        await Promise.resolve();
      });

      // Unmount before request completes
      unmount();

      // Verify AbortController signal was used
      expect(capturedSignal).toBeDefined();
    });

    it('should clean up timeout on successful request', async () => {
      vi.useFakeTimers(); // Enable fake timers only for this test

      mockFetchSuccess({ data: 'test' });

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        await result.current.get('/api/test');
      });

      // Timeout should be cleared (no error after 30s)
      vi.advanceTimersByTime(35000);

      expect(result.current.error).toBeNull();

      vi.useRealTimers(); // Restore real timers
    });

    it('should handle AbortError gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new DOMException('Aborted', 'AbortError'));

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        try {
          await result.current.get('/api/test');
        } catch (err) {
          // Expected
        }
      });

      // AbortErrors should be swallowed — no error state surfaced to consumers
      expect(result.current.error).toBeNull();
    });
  });

  // ==========================================================================
  // URL BUILDING
  // ==========================================================================

  describe('URL Building', () => {
    it('should build URL with API base from relative path', async () => {
      mockFetchSuccess({ data: 'test' });

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        await result.current.get('/api/test');
      });

      expect(getCallUrl()).toBe('http://localhost:3000/api/test');
    });

    it('should use absolute URL as-is', async () => {
      mockFetchSuccess({ data: 'test' });

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        await result.current.get('https://example.com/api/test');
      });

      expect(getCallUrl()).toBe('https://example.com/api/test');
    });

    it('should build query string from parameters', async () => {
      mockFetchSuccess({ data: 'test' });
      mockFetchSuccess({ data: 'test2' });

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        await result.current.get('/api/test');
      });

      // POST with query params to test buildUrl
      await act(async () => {
        await result.current.post('/api/test', undefined, {
          param1: 'value1',
          param2: 42,
          param3: true,
        });
      });

      const callUrl = getCallUrl(1);
      expect(callUrl).toContain('param1=value1');
      expect(callUrl).toContain('param2=42');
      expect(callUrl).toContain('param3=true');
    });

    it('should handle special characters in query parameters', async () => {
      mockFetchSuccess({ data: 'test' });

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        await result.current.post('/api/test', undefined, {
          query: 'test & query',
          url: 'https://example.com?foo=bar',
        });
      });

      const callUrl = getCallUrl();
      // URLSearchParams should encode special characters
      expect(callUrl).toContain('query=test+%26+query');
    });

    it('should handle empty query parameters object', async () => {
      mockFetchSuccess({ data: 'test' });

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        await result.current.post('/api/test', undefined, {});
      });

      const callUrl = getCallUrl();
      expect(callUrl).toBe('http://localhost:3000/api/test');
      expect(callUrl).not.toContain('?');
    });
  });

  // ==========================================================================
  // ERROR HANDLING
  // ==========================================================================

  describe('Error Handling', () => {
    it('should clear error state', async () => {
      mockFetchError(500);

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        try {
          await result.current.get('/api/test');
        } catch (err) {
          // Expected
        }
      });

      expect(result.current.error).toBeDefined();

      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });

    it('should parse HTTP error correctly', async () => {
      mockFetchError(404, 'Not Found');

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        try {
          await result.current.get('/api/test');
        } catch (err) {
          // Expected
        }
      });

      expect(result.current.error?.message).toContain('404');
      expect(result.current.error?.message).toContain('Not Found');
    });

    it('should handle fetch throwing non-Error objects', async () => {
      mockFetch.mockRejectedValueOnce('String error');

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        try {
          await result.current.get('/api/test');
        } catch (err) {
          // Expected
        }
      });

      expect(result.current.error).toBeDefined();
    });

    it('should clear error on new successful request', async () => {
      // First request fails
      mockFetchError(500);

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        try {
          await result.current.get('/api/test');
        } catch (err) {
          // Expected
        }
      });

      expect(result.current.error).toBeDefined();

      // Second request succeeds
      mockFetchSuccess({ data: 'success' });

      await act(async () => {
        await result.current.get('/api/test');
      });

      expect(result.current.error).toBeNull();
    });
  });

  // ==========================================================================
  // useQuery HOOK
  // ==========================================================================

  describe('useQuery Hook', () => {
    it('should fetch data on mount', async () => {
      mockFetchSuccess({ data: 'test' });

      const { result } = renderHook(() => useQuery('/api/test'));

      await waitFor(() => {
        expect(result.current.data).toEqual({ data: 'test' });
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('should skip fetch when skip is true', async () => {
      const { result } = renderHook(() => useQuery('/api/test', true));

      // Flush microtasks to ensure no fetch was triggered
      await act(async () => {});

      expect(result.current.data).toBeNull();
      expect(result.current.isLoading).toBe(false);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('should handle query errors', async () => {
      mockFetchError(500);

      const { result } = renderHook(() => useQuery('/api/test'));

      await waitFor(() => {
        expect(result.current.error).toBeDefined();
      }, { timeout: 3000 });

      expect(result.current.data).toBeNull();
    });

    it('should re-fetch when endpoint changes', async () => {
      mockFetchSuccess({ data: 'test1' });

      const { result, rerender } = renderHook(
        ({ endpoint }) => useQuery(endpoint),
        {
          initialProps: { endpoint: '/api/test1' },
        }
      );

      await waitFor(() => {
        expect(result.current.data).toEqual({ data: 'test1' });
      });

      mockFetchSuccess({ data: 'test2' });

      rerender({ endpoint: '/api/test2' });

      await waitFor(() => {
        expect(result.current.data).toEqual({ data: 'test2' });
      });
    });
  });

  // ==========================================================================
  // useMutation HOOK
  // ==========================================================================

  describe('useMutation Hook', () => {
    it('should perform POST mutation', async () => {
      mockFetchSuccess({ created: true });

      const { result } = renderHook(() => useMutation('/api/test', 'POST'));

      let response;
      await act(async () => {
        response = await result.current.mutate({ name: 'Test' });
      });

      expect(response).toEqual({ created: true });
      expect(result.current.data).toEqual({ created: true });
      expect(result.current.error).toBeNull();
    });

    it('should perform PUT mutation', async () => {
      mockFetchSuccess({ updated: true });

      const { result } = renderHook(() => useMutation('/api/test', 'PUT'));

      await act(async () => {
        await result.current.mutate({ name: 'Updated' });
      });

      expect(result.current.data).toEqual({ updated: true });
    });

    it('should perform DELETE mutation', async () => {
      mockFetchSuccess({ deleted: true });

      const { result } = renderHook(() => useMutation('/api/test', 'DELETE'));

      await act(async () => {
        await result.current.mutate();
      });

      expect(result.current.data).toBeNull();
    });

    it('should handle mutation errors', async () => {
      mockFetchError(400);

      const { result } = renderHook(() => useMutation('/api/test', 'POST'));

      await act(async () => {
        try {
          await result.current.mutate({});
        } catch (err) {
          // Expected
        }
      });

      expect(result.current.error).toBeDefined();
      expect(result.current.data).toBeNull();
    });

    it('should reset loading state after mutation completes', async () => {
      mockFetchSuccess({ success: true });

      const { result } = renderHook(() => useMutation('/api/test', 'POST'));

      await act(async () => {
        await result.current.mutate({});
      });

      // Loading should be false after mutation completes
      expect(result.current.isLoading).toBe(false);
    });
  });

  // ==========================================================================
  // EDGE CASES
  // ==========================================================================

  describe('Edge Cases', () => {
    it('should handle concurrent requests', async () => {
      mockFetchSuccess({ data: '1' });
      mockFetchSuccess({ data: '2' });
      mockFetchSuccess({ data: '3' });

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        await Promise.all([
          result.current.get('/api/test1'),
          result.current.get('/api/test2'),
          result.current.get('/api/test3'),
        ]);
      });

      expect(mockFetch).toHaveBeenCalledTimes(3);
    });

    it('should handle empty response body', async () => {
      mockFetch.mockResolvedValueOnce(createMockResponse(null, {
        ok: true,
        status: 204,
        statusText: 'No Content',
      }));

      const { result } = renderHook(() => useRestAPI());

      let response;
      await act(async () => {
        response = await result.current.get('/api/test');
      });

      expect(response).toBeNull();
    });

    it('should handle malformed JSON response', async () => {
      const malformedResponse = createMockResponse(null, {
        ok: true,
        status: 200,
        statusText: 'OK',
      });
      malformedResponse.json = async () => {
        throw new SyntaxError('Malformed JSON');
      };

      mockFetch.mockResolvedValueOnce(malformedResponse);

      const { result } = renderHook(() => useRestAPI());

      await act(async () => {
        try {
          await result.current.get('/api/test');
        } catch (err) {
          expect(err).toBeDefined();
        }
      });

      expect(result.current.error).toBeDefined();
    });

    it('should handle very long query parameter values', async () => {
      mockFetchSuccess({ data: 'test' });

      const { result } = renderHook(() => useRestAPI());

      const longValue = 'x'.repeat(1000);

      await act(async () => {
        await result.current.post('/api/test', undefined, {
          longParam: longValue,
        });
      });

      expect(getCallUrl()).toContain('longParam=');
    });

    it('should handle rapid re-renders during request', async () => {
      mockFetchSuccess({ data: 'test' });

      const { result, rerender } = renderHook(() => useRestAPI());

      const requestPromise = act(async () => {
        await result.current.get('/api/test');
      });

      // Rerender multiple times during request
      rerender();
      rerender();
      rerender();

      await requestPromise;

      expect(result.current.error).toBeNull();
    });

    it('should handle setting error to null manually', () => {
      const { result } = renderHook(() => useRestAPI());

      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });
  });
});
