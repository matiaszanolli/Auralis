/**
 * isRetryableError decides by HTTP status, not message text (#4467)
 *
 * It used to substring-match `error.message` for '502'/'503'/'429', so a
 * non-transient 4xx whose detail text contained one of those digits was
 * retried, while a transient failure worded differently was not.
 */

import { describe, it, expect } from 'vitest';

import { isRetryableError } from '../queryRetry';
import { APIRequestError } from '../apiRequest';

describe('isRetryableError (#4467)', () => {
  it('does NOT retry a 404 whose message happens to contain "502"', () => {
    const err = new APIRequestError('Track 502 not found', 404, 'Track 502 not found');
    expect(isRetryableError(err)).toBe(false);
  });

  it('does NOT retry a 400 mentioning "timeout" in its detail', () => {
    const err = new APIRequestError('timeout must be positive', 400);
    expect(isRetryableError(err)).toBe(false);
  });

  it.each([500, 502, 503, 504])('retries a %i', (status) => {
    expect(isRetryableError(new APIRequestError('Service trouble', status))).toBe(true);
  });

  it('does not retry 501 Not Implemented', () => {
    expect(isRetryableError(new APIRequestError('Not Implemented', 501))).toBe(false);
  });

  it.each([408, 429])('retries a %i even with unhelpful text', (status) => {
    expect(isRetryableError(new APIRequestError('Nope', status))).toBe(true);
  });

  it('retries apiRequest transport failures, which carry status 0', () => {
    expect(isRetryableError(new APIRequestError('Request timed out after 30000ms', 0))).toBe(true);
    expect(isRetryableError(new APIRequestError('Network error: boom', 0, 'boom'))).toBe(true);
  });

  it('does not retry a 200 that failed the response-shape check', () => {
    const err = new APIRequestError('Unexpected response shape from /api/x', 200);
    expect(isRetryableError(err)).toBe(false);
  });

  it('falls back to transport wording for errors without a status', () => {
    expect(isRetryableError(new TypeError('Failed to fetch'))).toBe(true);
    expect(isRetryableError(new Error('connection reset'))).toBe(true);
    expect(isRetryableError(new Error('503 in the message but no status'))).toBe(false);
    expect(isRetryableError(new Error('validation failed'))).toBe(false);
  });
});

describe('isRetryableError reads HttpStatusError.status (#5649)', () => {
  // httpErrorFromResponse builds a plain Error carrying `status`, not an
  // APIRequestError, so it used to fall through to the wording heuristic.
  const httpError = (status: number, message: string): Error =>
    Object.assign(new Error(message), { status });

  it.each([500, 503, 504, 408, 429])('retries a %i HttpStatusError even with unhelpful text', (status) => {
    expect(isRetryableError(httpError(status, 'Nope'))).toBe(true);
  });

  it('does NOT retry a 400 whose detail mentions "connection"', () => {
    expect(isRetryableError(httpError(400, 'connection string is invalid'))).toBe(false);
  });

  it('does not retry 501 or a 404', () => {
    expect(isRetryableError(httpError(501, 'Not Implemented'))).toBe(false);
    expect(isRetryableError(httpError(404, 'Track not found'))).toBe(false);
  });

  it('still falls back to transport wording for an error with no status', () => {
    expect(isRetryableError(new Error('Failed to fetch'))).toBe(true);
    expect(isRetryableError(new Error('Something else'))).toBe(false);
  });
});
