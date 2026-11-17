/**
 * retryTransient repeats only failures that can clear on their own (#5655).
 */

import { describe, it, expect, vi } from 'vitest';
import { retryTransient } from '../retryTransient';
import { APIRequestError } from '../apiRequest';

const FAST = { delaysMs: [1, 1] as const };

describe('retryTransient', () => {
  it('returns the first success without waiting', async () => {
    const attempt = vi.fn().mockResolvedValue('ok');
    await expect(retryTransient(attempt, FAST)).resolves.toBe('ok');
    expect(attempt).toHaveBeenCalledTimes(1);
  });

  it('retries a transport failure and a 503, then succeeds', async () => {
    const attempt = vi.fn()
      .mockRejectedValueOnce(new APIRequestError('Network error: down', 0))
      .mockRejectedValueOnce(new APIRequestError('unavailable', 503))
      .mockResolvedValue('ok');
    await expect(retryTransient(attempt, FAST)).resolves.toBe('ok');
    expect(attempt).toHaveBeenCalledTimes(3);
  });

  it('gives up after the configured retries and rethrows the last error', async () => {
    const attempt = vi.fn().mockRejectedValue(new APIRequestError('still down', 502));
    await expect(retryTransient(attempt, FAST)).rejects.toThrow('still down');
    expect(attempt).toHaveBeenCalledTimes(3);
  });

  it('does not repeat a 404, a bad response shape or an abort', async () => {
    for (const error of [
      new APIRequestError('missing', 404),
      new APIRequestError('Unexpected response shape', 200),
      Object.assign(new Error('aborted'), { name: 'AbortError' }),
    ]) {
      const attempt = vi.fn().mockRejectedValue(error);
      await expect(retryTransient(attempt, FAST)).rejects.toBe(error);
      expect(attempt).toHaveBeenCalledTimes(1);
    }
  });

  it('stops retrying once the caller has gone away', async () => {
    let cancelled = false;
    const attempt = vi.fn().mockImplementation(async () => {
      cancelled = true;
      throw new APIRequestError('down', 0);
    });
    await expect(retryTransient(attempt, { ...FAST, isCancelled: () => cancelled })).rejects.toThrow('down');
    expect(attempt).toHaveBeenCalledTimes(1);
  });
});
