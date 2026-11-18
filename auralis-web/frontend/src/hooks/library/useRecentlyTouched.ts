/**
 * useRecentlyTouched Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tracks and manages recently accessed albums using localStorage.
 * Provides methods to record album access and retrieve recent albums.
 *
 * Features:
 * - Persists across browser sessions via localStorage
 * - Maintains sorted list by access time (most recent first)
 * - Limits storage to prevent bloat (default: 20 albums)
 * - Deduplicates entries (same album touched twice = update timestamp only)
 */

import { useState, useCallback, useEffect, useRef } from 'react';

const STORAGE_KEY = 'auralis-recently-touched-albums';
const MAX_RECENT = 20;

interface RecentlyTouchedEntry {
  albumId: number;
  albumTitle: string;
  artist: string;
  touchedAt: number; // Unix timestamp
}

/**
 * Load recently touched albums from localStorage
 */
const loadRecentlyTouched = (): RecentlyTouchedEntry[] => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return [];
    const parsed = JSON.parse(stored);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

/**
 * Save recently touched albums to localStorage
 */
const saveRecentlyTouched = (entries: RecentlyTouchedEntry[]): void => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Silently fail if localStorage is full
  }
};

/**
 * Hook to track recently accessed albums
 *
 * @example
 * ```tsx
 * const { recentAlbums, touchAlbum } = useRecentlyTouched();
 *
 * // When user clicks an album
 * touchAlbum(albumId, albumTitle, artist);
 *
 * // Display recent albums
 * recentAlbums.map(album => <RecentAlbumCard key={album.albumId} {...album} />)
 * ```
 */
export function useRecentlyTouched() {
  const [recentAlbums, setRecentAlbums] = useState<RecentlyTouchedEntry[]>(() =>
    loadRecentlyTouched()
  );
  // The latest list, so touchAlbum computes its next value and persists it outside a
  // setState updater, which React may run twice (StrictMode) or defer (#6429). Every
  // write goes through `commit`, which keeps the ref and the state in step.
  const recentRef = useRef(recentAlbums);
  const commit = useCallback((next: RecentlyTouchedEntry[]) => {
    recentRef.current = next;
    setRecentAlbums(next);
  }, []);

  // Sync with localStorage changes from other tabs
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) {
        commit(loadRecentlyTouched());
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [commit]);

  /**
   * Record an album as recently touched
   * Moves to top if already present, adds if new
   */
  const touchAlbum = useCallback((albumId: number, albumTitle: string, artist: string) => {
    // Remove existing entry for this album (if any), add the new one at the
    // beginning, and limit to MAX_RECENT entries.
    const filtered = recentRef.current.filter(entry => entry.albumId !== albumId);
    const newEntry: RecentlyTouchedEntry = {
      albumId,
      albumTitle,
      artist,
      touchedAt: Date.now(),
    };
    const updated = [newEntry, ...filtered].slice(0, MAX_RECENT);

    commit(updated);
    saveRecentlyTouched(updated);
  }, [commit]);

  /**
   * Clear all recently touched albums
   */
  const clearRecent = useCallback(() => {
    commit([]);
    localStorage.removeItem(STORAGE_KEY);
  }, [commit]);

  return {
    recentAlbums,
    touchAlbum,
    clearRecent,
  };
}

export type { RecentlyTouchedEntry };
