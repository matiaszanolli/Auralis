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
