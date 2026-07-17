/**
 * useLibraryWithStats - Library Data and Statistics Composition Hook
 *
 * Composes useLibraryPagination, useLibraryStats, and useLibraryScan into the
 * unified interface consumed by CozyLibraryView. Callers are unaffected by the
 * internal decomposition (#3645).
 */

import { useEffect, useCallback } from 'react';
import { useWebSocketSubscription } from '@/hooks/websocket/useWebSocketSubscription';
import { isElectron } from '@/utils/electron';
import type { LibraryStats, LibraryTrack } from '@/types/domain';
import { useLibraryPagination } from './useLibraryPagination';
import { useLibraryStats } from './useLibraryStats';
import { useLibraryScan } from './useLibraryScan';

export type { LibraryStats };

export interface UseLibraryWithStatsOptions {
  view: string;
  autoLoad?: boolean;
  includeStats?: boolean;
}

export interface UseLibraryWithStatsReturn {
  tracks: LibraryTrack[];
  stats: LibraryStats | null;
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  totalTracks: number;
  offset: number;
  isLoadingMore: boolean;
  scanning: boolean;
  statsLoading: boolean;
  statsError: string | null;
  fetchTracks: (resetPagination?: boolean) => Promise<void>;
  loadMore: () => Promise<void>;
  handleScanFolder: () => Promise<void>;
  refetchStats: () => Promise<void>;
  webFolderPath: string;
  setWebFolderPath: (path: string) => void;
  isElectron: () => boolean;
}

export const useLibraryWithStats = ({
  view,
  autoLoad = true,
  includeStats = true,
}: UseLibraryWithStatsOptions): UseLibraryWithStatsReturn => {
  // Abort refs are pulled out of the spreads only to keep them out of the public
  // return; each sub-hook owns its own abort lifecycle (it aborts its previous
  // request on every new call AND on unmount), so the parent no longer aborts
  // them (#4193 — the old parent cleanup was a redundant double-abort).
  const { fetchTracks, loadMore, fetchAbortRef: _fetchAbortRef, ...paginationState } = useLibraryPagination({ view });
  const { refetchStats, statsAbortRef: _statsAbortRef, ...statsState } = useLibraryStats({ includeStats });
  const { handleScanFolder, scanAbortRef: _scanAbortRef, ...scanState } = useLibraryScan({
    includeStats,
    fetchTracks,
    refetchStats,
  });

  // Auto-load on mount or when view/options change. Sub-hooks own their own
  // abort-on-unmount and abort-on-new-call; this effect only drives the load.
  useEffect(() => {
    if (autoLoad) {
      fetchTracks();
      if (includeStats) refetchStats();
    }
  }, [view, autoLoad, includeStats, fetchTracks, refetchStats]);

  // Refresh library data when backend broadcasts library_updated (#2871).
  const handleLibraryUpdated = useCallback(() => {
    fetchTracks();
    if (includeStats) refetchStats();
  }, [fetchTracks, includeStats, refetchStats]);

  useWebSocketSubscription(['library_updated'], handleLibraryUpdated);

  return {
    ...paginationState,
    ...statsState,
    ...scanState,
    fetchTracks,
    loadMore,
    handleScanFolder,
    refetchStats,
    isElectron: () => isElectron(),
  };
};

export default useLibraryWithStats;
