/**
 * "Scan Now" must outlive the shared 30s request timeout (#5643)
 *
 * Settings' triggerLibraryScan awaits POST /api/library/scan for the length of
 * the scan. Since #4820 the backend stops the scan when the client disconnects,
 * so the 30s DEFAULT_TIMEOUT_MS aborting that fetch killed any scan past 30
 * seconds and the dialog reported "Failed to start scan". settingsService.test
 * mocks the transport; this drives the real apiRequest with a fake fetch.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { triggerLibraryScan } from '../settingsService';
import { DEFAULT_TIMEOUT_MS } from '@/utils/apiRequest';

describe('triggerLibraryScan against the real transport (#5643)', () => {
  let signal: AbortSignal | undefined;
  let finishScan: (() => void) | undefined;

  beforeEach(() => {
    vi.useFakeTimers();
    signal = undefined;
    finishScan = undefined;
    vi.stubGlobal('fetch', vi.fn((_url: string, init?: RequestInit) => {
      signal = init?.signal ?? undefined;
      return new Promise<Response>((resolve, reject) => {
        signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
        finishScan = () => resolve(new Response(JSON.stringify({ files_added: 3 }), { status: 200 }));
      });
    }));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('keeps the request open past the 30s default and resolves when the scan finishes', async () => {
    const result = triggerLibraryScan(['/music']);
    result.catch(() => undefined);

    await vi.advanceTimersByTimeAsync(DEFAULT_TIMEOUT_MS + 1_000);

    expect(signal?.aborted).toBe(false);

    finishScan!();
    await expect(result).resolves.toBeUndefined();
  });

  it('still bounds the request (a hung server does not hold it open forever)', async () => {
    const result = triggerLibraryScan(['/music']);
    const settled = result.then(() => 'ok', () => 'aborted');

    await vi.advanceTimersByTimeAsync(3_700_000);

    expect(signal?.aborted).toBe(true);
    await expect(settled).resolves.toBe('aborted');
  });
});
