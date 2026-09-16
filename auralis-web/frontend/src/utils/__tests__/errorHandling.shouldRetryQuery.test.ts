/**
 * React Query retries only retryable errors (#5387)
 *
 * The global QueryClient used `retry: 1`, so a 404 or 400 cost a second
 * identical round trip before surfacing. It now uses shouldRetryQuery, which
 * applies isRetryableError's status rule and keeps the one-retry cap.
 */

import { describe, it, expect, vi } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import { APIRequestError } from '@/utils/apiRequest';
import { MAX_QUERY_RETRIES, shouldRetryQuery } from '../errorHandling';

const httpError = (status: number) => new APIRequestError(`HTTP ${status}`, status);

/** Run one query through a real QueryClient and count fetch attempts. */
async function attemptsFor(errors: Error[]): Promise<number> {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: shouldRetryQuery, retryDelay: 0 } },
  });
  const queryFn = vi.fn(async () => {
    const next = errors[Math.min(queryFn.mock.calls.length - 1, errors.length - 1)];
    if (next) throw next;
    return 'ok';
  });
  await client.fetchQuery({ queryKey: ['probe'], queryFn }).catch(() => undefined);
  client.clear();
  return queryFn.mock.calls.length;
}

describe('shouldRetryQuery (#5387)', () => {
  it('does not retry a 404 or 400', async () => {
    expect(await attemptsFor([httpError(404)])).toBe(1);
    expect(await attemptsFor([httpError(400)])).toBe(1);
  });

  it('retries a 503, 429 and a transport failure once', async () => {
    expect(await attemptsFor([httpError(503)])).toBe(1 + MAX_QUERY_RETRIES);
    expect(await attemptsFor([httpError(429)])).toBe(1 + MAX_QUERY_RETRIES);
    expect(await attemptsFor([httpError(0)])).toBe(1 + MAX_QUERY_RETRIES);
  });

  it('stops after the retry budget even if the error stays retryable', () => {
    expect(shouldRetryQuery(0, httpError(503))).toBe(true);
    expect(shouldRetryQuery(MAX_QUERY_RETRIES, httpError(503))).toBe(false);
  });

  it('accepts a non-Error rejection without throwing', () => {
    expect(shouldRetryQuery(0, 'network down')).toBe(true);
    expect(shouldRetryQuery(0, { status: 404 })).toBe(false);
  });
});
