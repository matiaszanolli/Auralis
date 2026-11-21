/**
 * The scan request's client bound follows the server's configured bound (#6576).
 *
 * SCAN_TIMEOUT_MS was a literal for the backend's DEFAULT (3600s + 60s), but the server's bound is
 * AURALIS_SCAN_TIMEOUT, which can be raised. Since #4820 an aborted scan request stops the scan, so
 * with the server configured for longer, the client aborted at 61 minutes and the scan died as a
 * "client disconnect". The server now reports scan_timeout_s and the client bound is derived from it.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/utils/apiRequest', () => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }));

async function load() {
  vi.resetModules();
  const api = await import('@/utils/apiRequest');
  const module = await import('../scanRequestTimeout');
  const config = await import('@/config/api');
  return { get: vi.mocked(api.get), post: vi.mocked(api.post), ...module, ...config };
}

describe('scanRequestTimeoutMs (#6576)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('exceeds the bound the server reports, so the server always answers first', async () => {
    const { get, scanRequestTimeoutMs, knownScanRequestTimeoutMs, ENDPOINTS } = await load();
    get.mockResolvedValue({ is_scanning: false, scan_timeout_s: 7200 });

    const bound = await scanRequestTimeoutMs();

    expect(bound).toBeGreaterThan(7200 * 1000);
    expect(bound).toBe(7200 * 1000 + 60_000);
    expect(get).toHaveBeenCalledWith(ENDPOINTS.LIBRARY_SCAN_STATUS, expect.anything());
    expect(knownScanRequestTimeoutMs()).toBe(bound);
  });

  it('reads the server bound once, then reuses it', async () => {
    const { get, scanRequestTimeoutMs } = await load();
    get.mockResolvedValue({ scan_timeout_s: 7200 });

    await scanRequestTimeoutMs();
    await scanRequestTimeoutMs();

    expect(get).toHaveBeenCalledTimes(1);
  });

  it('uses the status resync’s report without a request of its own', async () => {
    const { get, recordScanTimeout, scanRequestTimeoutMs } = await load();

    recordScanTimeout(10_800);

    expect(await scanRequestTimeoutMs()).toBe(10_800 * 1000 + 60_000);
    expect(get).not.toHaveBeenCalled();
  });

  it('falls back to the default server’s bound when the read fails, and asks again next time', async () => {
    const { get, scanRequestTimeoutMs, knownScanRequestTimeoutMs, SCAN_TIMEOUT_MS } = await load();
    get.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ scan_timeout_s: 7200 });

    expect(await scanRequestTimeoutMs()).toBe(SCAN_TIMEOUT_MS);
    expect(knownScanRequestTimeoutMs()).toBeNull();
    expect(await scanRequestTimeoutMs()).toBe(7200 * 1000 + 60_000);
  });

  it('ignores a missing or nonsensical reported bound', async () => {
    const { recordScanTimeout, knownScanRequestTimeoutMs } = await load();

    for (const bad of [undefined, 0, -5, Number.NaN, '3600']) recordScanTimeout(bad);

    expect(knownScanRequestTimeoutMs()).toBeNull();
  });

  it('propagates a cancellation instead of falling back', async () => {
    const { get, scanRequestTimeoutMs } = await load();
    get.mockRejectedValue(new DOMException('aborted', 'AbortError'));

    await expect(scanRequestTimeoutMs()).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('triggerLibraryScan posts with the derived bound', async () => {
    const { get, post } = await load();
    get.mockResolvedValue({ scan_timeout_s: 7200 });
    post.mockResolvedValue({});
    const settingsService = await import('../settingsService');

    await settingsService.triggerLibraryScan(['/music']);

    expect(post).toHaveBeenCalledWith(
      '/api/library/scan',
      { directories: ['/music'], recursive: true, skip_existing: true },
      { timeoutMs: 7200 * 1000 + 60_000 },
    );
  });
});
