/**
 * useLibraryScan tests (#4185)
 *
 * Covers the web folder-scan flow: missing-path guard, success (toast +
 * fetchTracks/refetchStats), failure toast, abort-on-unmount, and
 * abort-on-supersede. (Electron path is not exercised — jsdom is non-electron.)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useLibraryScan } from '../useLibraryScan';
import { useToast } from '@/components/shared/Toast';
import { DEFAULT_TIMEOUT_MS } from '@/utils/apiRequest';

/** A request that never settles until the transport's timeout aborts it. */
const hangingImpl = (_url: string, init: RequestInit) =>
  new Promise((_resolve, reject) => {
    init.signal?.addEventListener('abort', () => {
      reject(Object.assign(new Error('aborted'), { name: 'AbortError' }));
    });
  });


vi.mock('@/components/shared/Toast', () => ({ useToast: vi.fn() }));
vi.mock('@/utils/electron', () => ({
  isElectron: () => false,
  getElectronAPI: () => null,
}));

const mockSuccess = vi.fn();
const mockError = vi.fn();
const mockInfo = vi.fn();
const fetchTracks = vi.fn().mockResolvedValue(undefined);
const refetchStats = vi.fn().mockResolvedValue(undefined);
let mockFetch: ReturnType<typeof vi.fn>;

function setup(includeStats = true) {
  return renderHook(() => useLibraryScan({ includeStats, fetchTracks, refetchStats }));
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useToast).mockReturnValue({ success: mockSuccess, error: mockError, info: mockInfo } as any);
  mockFetch = vi.fn();
  vi.stubGlobal('fetch', mockFetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useLibraryScan (#4185)', () => {
  it('shows an info toast and does not fetch when no folder path is entered', async () => {
    const { result } = setup();
    await act(async () => {
      await result.current.handleScanFolder();
    });
    expect(mockInfo).toHaveBeenCalled();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('posts the scan, toasts success, and refreshes tracks + stats', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({ files_added: 5 }) });

    const { result } = setup(true);
    act(() => result.current.setWebFolderPath('/music'));
    await act(async () => {
      await result.current.handleScanFolder();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/library/scan',
      expect.objectContaining({ method: 'POST', signal: expect.any(AbortSignal) })
    );
    expect(mockSuccess).toHaveBeenCalledWith(expect.stringContaining('5'));
    expect(fetchTracks).toHaveBeenCalled();
    expect(refetchStats).toHaveBeenCalled();
    expect(result.current.scanning).toBe(false);
  });

  it('does not refetch stats when includeStats is false', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({ files_added: 1 }) });

    const { result } = setup(false);
    act(() => result.current.setWebFolderPath('/music'));
    await act(async () => {
      await result.current.handleScanFolder();
    });

    expect(fetchTracks).toHaveBeenCalled();
    expect(refetchStats).not.toHaveBeenCalled();
  });

  it('shows an error toast when the scan request fails', async () => {
    mockFetch.mockResolvedValue({ ok: false, json: async () => ({ detail: 'boom' }) });

    const { result } = setup();
    act(() => result.current.setWebFolderPath('/music'));
    await act(async () => {
      await result.current.handleScanFolder();
    });

    expect(mockError).toHaveBeenCalledWith(expect.stringContaining('boom'));
  });

  it('surfaces failed/skipped counts in the completion toast (#4412)', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ files_added: 5, files_failed: 3, files_skipped: 2 }),
    });

    const { result } = setup();
    act(() => result.current.setWebFolderPath('/music'));
    await act(async () => {
      await result.current.handleScanFolder();
    });

    // Nonzero failures escalate to an error toast that names the counts.
    expect(mockError).toHaveBeenCalledWith(expect.stringContaining('3 failed'));
    expect(mockError).toHaveBeenCalledWith(expect.stringContaining('2 skipped'));
    expect(mockSuccess).not.toHaveBeenCalled();
  });

  it('stops scanning with an error toast when the request times out (#5019)', async () => {
    // Pre-#5019 the POST went through a bare fetch(): its AbortController only
    // fired on unmount or supersede, so a hung backend left `scanning` true
    // (and the scan button disabled) with no toast, indefinitely.
    vi.useFakeTimers();
    try {
      mockFetch.mockImplementation(hangingImpl);

      const { result } = setup();
      act(() => result.current.setWebFolderPath('/music'));
      let pending!: Promise<void>;
      act(() => {
        pending = result.current.handleScanFolder();
      });
      expect(result.current.scanning).toBe(true);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(DEFAULT_TIMEOUT_MS);
        await pending;
      });

      expect(result.current.scanning).toBe(false);
      // A timeout is a transport failure (statusCode 0), so it takes the
      // "backend unreachable" arm rather than the `Scan failed: <detail>` one.
      expect(mockError).toHaveBeenCalledWith(expect.stringContaining('Error scanning folder'));
    } finally {
      vi.useRealTimers();
    }
  });

  it('aborts the in-flight scan on unmount', async () => {
    let signal: AbortSignal | undefined;
    mockFetch.mockImplementation((_url: string, opts: RequestInit) => {
      signal = opts.signal as AbortSignal;
      return new Promise(() => {});
    });

    const { result, unmount } = setup();
    act(() => result.current.setWebFolderPath('/music'));
    act(() => {
      void result.current.handleScanFolder();
    });
    expect(signal!.aborted).toBe(false);

    unmount();
    expect(signal!.aborted).toBe(true);
  });

  it('aborts a prior scan when a new one supersedes it', async () => {
    const signals: AbortSignal[] = [];
    mockFetch.mockImplementation((_url: string, opts: RequestInit) => {
      signals.push(opts.signal as AbortSignal);
      return new Promise(() => {});
    });

    const { result } = setup();
    act(() => result.current.setWebFolderPath('/music'));
    act(() => {
      void result.current.handleScanFolder();
    });
    act(() => {
      void result.current.handleScanFolder();
    });

    expect(signals).toHaveLength(2);
    expect(signals[0].aborted).toBe(true); // superseded
    expect(signals[1].aborted).toBe(false);
  });
});
