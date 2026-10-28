/**
 * useLibraryChangeSync (#5871): a library change re-reads the album caches.
 *
 * Nothing invalidated `['albums']`, so under the 5-minute staleTime the album
 * grid kept the pre-scan set after a scan and pre-edit titles after an edit.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';

let deliver: ((message: unknown) => void) | undefined;

vi.mock('@/hooks/websocket/useWebSocketMessages', () => ({
  useWebSocketMessages: vi.fn((_types: string[], callback: (msg: unknown) => void) => {
    deliver = callback;
  }),
}));

import { useWebSocketMessages } from '@/hooks/websocket/useWebSocketMessages';
import { LIBRARY_CHANGE_MESSAGES, useLibraryChangeSync } from '../useLibraryChangeSync';

describe('useLibraryChangeSync', () => {
  let queryClient: QueryClient;
  let invalidate: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    deliver = undefined;
    queryClient = new QueryClient();
    invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children);
    renderHook(() => useLibraryChangeSync(), { wrapper });
  });

  it('subscribes to every frame that can change browse data', () => {
    expect(useWebSocketMessages).toHaveBeenCalledWith(LIBRARY_CHANGE_MESSAGES, expect.any(Function));
    expect(LIBRARY_CHANGE_MESSAGES).toEqual(
      expect.arrayContaining(['library_updated', 'metadata_updated', 'metadata_batch_updated', 'library_tracks_removed'])
    );
  });

  it('a scan invalidates the albums and the album fingerprints', () => {
    deliver?.({ type: 'library_updated', data: { action: 'scan' } });

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['albums'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['album-fingerprint'] });
  });

  it('a metadata edit invalidates the albums but leaves fingerprints cached', () => {
    deliver?.({ type: 'metadata_updated', data: { track_id: 1, updated_fields: ['year'] } });

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['albums'] });
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ['album-fingerprint'] });
  });
});
