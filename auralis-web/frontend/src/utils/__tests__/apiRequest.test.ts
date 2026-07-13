/**
 * apiRequest Utility Tests (#4452)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Direct coverage for the shared HTTP client used by every service. Every
 * service test mocks `@/utils/apiRequest` wholesale, so before this file the
 * real 204 short-circuit, error-body extraction, non-JSON fallback and
 * `APIRequestError` wrapping never executed under test.
 *
 * These tests drive the REAL `apiRequest()` against a mocked `global.fetch`,
 * covering the five branches: 200/JSON, 204 No Content, 4xx with a JSON error
 * body, 4xx with a non-JSON body, and a network-level reject.
 *
 * WIRING: this file intentionally does NOT `vi.mock('@/utils/apiRequest')` —
 * the module under test must be the real implementation.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { apiRequest, get, post, del, APIRequestError } from '../apiRequest';

// ----------------------------------------------------------------------------
// Fetch mocking helpers
// ----------------------------------------------------------------------------

/** Build a minimal Response-like object for the happy/error paths. */
function makeResponse(init: {
  ok: boolean;
  status: number;
  statusText?: string;
  json?: () => Promise<unknown>;
}): Response {
  return {
    ok: init.ok,
    status: init.status,
    statusText: init.statusText ?? '',
    json: init.json ?? (async () => ({})),
  } as unknown as Response;
}

describe('apiRequest (#4452)', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  const mockedFetch = () => vi.mocked(globalThis.fetch);

  // --------------------------------------------------------------------------
  // 1. 200 / JSON — parsed body is returned
  // --------------------------------------------------------------------------

  it('returns the parsed JSON body on a 200 response', async () => {
    const payload = { id: 1, name: 'Track' };
    mockedFetch().mockResolvedValue(
      makeResponse({ ok: true, status: 200, json: async () => payload })
    );

    const result = await apiRequest<typeof payload>('/library/tracks/1');

    expect(result).toEqual(payload);
    // Default headers + JSON content type are applied.
    const [, options] = mockedFetch().mock.calls[0];
    expect(options?.headers).toMatchObject({ 'Content-Type': 'application/json' });
  });

  it('serialises a body object and sets the method via post()', async () => {
    mockedFetch().mockResolvedValue(
      makeResponse({ ok: true, status: 200, json: async () => ({ ok: true }) })
    );

    await post('/playlists', { name: 'My Playlist' });

    const [, options] = mockedFetch().mock.calls[0];
    expect(options?.method).toBe('POST');
    expect(options?.body).toBe(JSON.stringify({ name: 'My Playlist' }));
  });

  // --------------------------------------------------------------------------
  // 2. 204 No Content — short-circuits before json()
  // --------------------------------------------------------------------------

  it('returns undefined on a 204 without calling response.json()', async () => {
    const json = vi.fn(async () => ({ shouldNotBeRead: true }));
    mockedFetch().mockResolvedValue(makeResponse({ ok: true, status: 204, json }));

    const result = await del('/playlists/1');

    expect(result).toBeUndefined();
    expect(json).not.toHaveBeenCalled();
  });

  // --------------------------------------------------------------------------
  // 3. 4xx with a JSON error body — detail/message extraction
  // --------------------------------------------------------------------------

  it('throws APIRequestError with the extracted detail on a 4xx JSON body', async () => {
    mockedFetch().mockResolvedValue(
      makeResponse({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: async () => ({ detail: 'Playlist not found' }),
      })
    );

    await expect(get('/playlists/999')).rejects.toMatchObject({
      name: 'APIRequestError',
      message: 'Playlist not found',
      statusCode: 404,
      detail: 'Playlist not found',
    });
  });

  it('falls back to the `message` field when `detail` is absent', async () => {
    mockedFetch().mockResolvedValue(
      makeResponse({
        ok: false,
        status: 422,
        json: async () => ({ message: 'Validation failed' }),
      })
    );

    await expect(apiRequest('/x')).rejects.toMatchObject({
      message: 'Validation failed',
      statusCode: 422,
    });
  });

  // --------------------------------------------------------------------------
  // 4. 4xx with a non-JSON body — status/statusText fallback
  // --------------------------------------------------------------------------

  it('falls back to "<status> <statusText>" when the error body is not JSON', async () => {
    mockedFetch().mockResolvedValue(
      makeResponse({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: async () => {
          throw new SyntaxError('Unexpected token < in JSON');
        },
      })
    );

    await expect(apiRequest('/boom')).rejects.toMatchObject({
      name: 'APIRequestError',
      message: '500 Internal Server Error',
      statusCode: 500,
      detail: undefined,
    });
  });

  // --------------------------------------------------------------------------
  // 5. Network-level reject — wrapped as APIRequestError(status 0)
  // --------------------------------------------------------------------------

  it('wraps a network-level fetch reject as an APIRequestError with status 0', async () => {
    mockedFetch().mockRejectedValue(new TypeError('Failed to fetch'));

    const error = (await apiRequest('/offline').catch((e) => e)) as APIRequestError;

    expect(error).toBeInstanceOf(APIRequestError);
    expect(error.message).toBe('Network error: Failed to fetch');
    expect(error.statusCode).toBe(0);
    expect(error.detail).toBe('Failed to fetch');
  });

  it('does not double-wrap an APIRequestError raised in the try block', async () => {
    // A 4xx path throws APIRequestError inside the try; the outer catch must
    // re-throw it unchanged rather than re-wrapping it as a network error.
    mockedFetch().mockResolvedValue(
      makeResponse({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Forbidden' }),
      })
    );

    const error = (await apiRequest('/secret').catch((e) => e)) as APIRequestError;

    expect(error).toBeInstanceOf(APIRequestError);
    expect(error.statusCode).toBe(403);
    expect(error.message).toBe('Forbidden');
  });
});
