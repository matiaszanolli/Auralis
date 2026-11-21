/**
 * A request cancelled while its body is being read rejects with an AbortError (#6450).
 *
 * `apiRequest` rethrows a caller abort as a raw AbortError (#5653), but `fetchWithTimeout` stops
 * following the caller's signal once headers arrive. A request cancelled during the body read
 * therefore finishes normally, and a non-2xx one came out as an `APIRequestError` carrying the
 * HTTP status (as did a failed `validate`), so callers could not tell it from a real failure and
 * re-checked their own signal at every call site.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { get, APIRequestError } from '../apiRequest';
import { isAbortError } from '../errorGuards';

/** A response whose body read stays pending until `finishBody` is called, then yields `body`. */
function slowResponse(init: { ok: boolean; status: number }, body: unknown) {
  let finishBody!: () => void;
  const pending = new Promise<void>((resolve) => {
    finishBody = resolve;
  });
  const response = {
    ...init,
    statusText: 'Status',
    json: () => pending.then(() => body),
  } as unknown as Response;
  return { response, finishBody };
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('a caller abort during the body read (#6450)', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const fetchReturns = (response: Response) => vi.mocked(globalThis.fetch).mockResolvedValue(response);

  async function cancelledDuringBody<T>(response: Response, finishBody: () => void, options: Parameters<typeof get<T>>[1] = {}) {
    fetchReturns(response);
    const controller = new AbortController();
    const request = get<T>('/api/library/tracks', { ...options, signal: controller.signal });
    await settle(); // headers are in; the body read is pending
    controller.abort();
    finishBody();
    return request.catch((e: unknown) => e);
  }

  it('a non-2xx body rejects with an AbortError, not an APIRequestError carrying the status', async () => {
    const { response, finishBody } = slowResponse({ ok: false, status: 500 }, { detail: 'boom' });

    const error = await cancelledDuringBody(response, finishBody);

    expect(isAbortError(error)).toBe(true);
    expect(error).not.toBeInstanceOf(APIRequestError);
  });

  it('a failed shape check rejects with an AbortError too', async () => {
    const { response, finishBody } = slowResponse({ ok: true, status: 200 }, { unexpected: true });

    const error = await cancelledDuringBody(response, finishBody, { validate: (_v: unknown): _v is never => false });

    expect(isAbortError(error)).toBe(true);
  });

  it('an uncancelled non-2xx request is still a status-bearing APIRequestError', async () => {
    const { response, finishBody } = slowResponse({ ok: false, status: 500 }, { detail: 'boom' });
    fetchReturns(response);

    const request = get('/api/library/tracks', { signal: new AbortController().signal }).catch((e: unknown) => e);
    await settle();
    finishBody();
    const error = await request;

    expect(error).toBeInstanceOf(APIRequestError);
    expect((error as APIRequestError).statusCode).toBe(500);
    expect((error as APIRequestError).message).toBe('boom');
  });

  it('an uncancelled failed shape check is still an APIRequestError', async () => {
    const { response, finishBody } = slowResponse({ ok: true, status: 200 }, { unexpected: true });
    fetchReturns(response);

    const request = get('/api/library/tracks', { validate: (_v: unknown): _v is never => false }).catch((e: unknown) => e);
    await settle();
    finishBody();

    expect(await request).toBeInstanceOf(APIRequestError);
  });

  it('a request already aborted before it starts rejects with an AbortError', async () => {
    vi.mocked(globalThis.fetch).mockRejectedValue(new DOMException('aborted', 'AbortError'));
    const controller = new AbortController();
    controller.abort();

    expect(isAbortError(await get('/x', { signal: controller.signal }).catch((e: unknown) => e))).toBe(true);
  });
});
