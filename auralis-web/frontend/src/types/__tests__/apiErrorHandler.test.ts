/**
 * ApiErrorHandler.parse() — status extraction across both HTTP transports (#4643)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The app has two HTTP transports with two different "carry the real status"
 * conventions: `hooks/api/useRestAPI.ts` attaches it as `.status` (via
 * `httpErrorFromResponse`'s `HttpStatusError`, #4831), while
 * `utils/apiRequest.ts`'s `APIRequestError` attaches it as `.statusCode`.
 * `ApiErrorHandler.parse()` only checked `.status` until #4643, so every
 * caller combining `get()`/`post()`/etc. from `apiRequest.ts` with
 * `ApiErrorHandler.parse()` silently got the 500 default back regardless of
 * the real HTTP status — a correctness gap nothing had exercised yet, since
 * useAlbumDetails.ts/useArtistDetailsData.ts (#4643) were the first callers
 * to combine the two.
 */

import { describe, it, expect } from 'vitest';
import { ApiErrorHandler } from '../api';
import { APIRequestError } from '@/utils/apiRequest';

describe('ApiErrorHandler.parse', () => {
  it('reads .status from a useRestAPI-shaped error (#4831)', () => {
    const err = Object.assign(new Error('Album 999 not found'), { status: 404 });

    const parsed = ApiErrorHandler.parse(err);

    expect(parsed).toEqual({ status: 404, message: 'Album 999 not found' });
  });

  it('reads .statusCode from an APIRequestError (apiRequest.ts, #4643)', () => {
    const err = new APIRequestError('Album 999 not found', 404, 'Album 999 not found');

    const parsed = ApiErrorHandler.parse(err);

    expect(parsed).toEqual({ status: 404, message: 'Album 999 not found' });
  });

  it('distinguishes a 500 APIRequestError from a 404 one', () => {
    const notFound = ApiErrorHandler.parse(new APIRequestError('Not found', 404));
    const serverError = ApiErrorHandler.parse(new APIRequestError('Boom', 500));

    expect(ApiErrorHandler.isNotFound(notFound)).toBe(true);
    expect(ApiErrorHandler.isNotFound(serverError)).toBe(false);
    expect(ApiErrorHandler.isNetworkError(serverError)).toBe(true);
    expect(ApiErrorHandler.isNetworkError(notFound)).toBe(false);
  });

  it('falls back to scraping a legacy "HTTP nnn:" message when neither property is present', () => {
    const err = new Error('HTTP 503: Service Unavailable');

    const parsed = ApiErrorHandler.parse(err);

    expect(parsed).toEqual({ status: 503, message: 'HTTP 503: Service Unavailable' });
  });

  it('defaults to 500 for a plain Error with no status information at all', () => {
    const parsed = ApiErrorHandler.parse(new Error('something broke'));

    expect(parsed.status).toBe(500);
  });

  it('does not misread a non-Error, non-ApiError-shaped value as status 0 via .statusCode', () => {
    // A bare object with an unrelated numeric `statusCode`-named field should
    // not be treated as an ApiError shape (isApiError requires `status`, not
    // `statusCode`) — parse() only special-cases Error instances and the
    // `{status, message}` shape, so this exercises the final catch-all.
    const parsed = ApiErrorHandler.parse({ statusCode: 404, message: 'looks like an error' });

    expect(parsed.status).toBe(500);
  });
});
