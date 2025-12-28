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

import { useState, useCallback, useEffect } from 'react';

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

  // Sync with localStorage changes from other tabs
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) {
        setRecentAlbums(loadRecentlyTouched());
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  /**
   * Record an album as recently touched
   * Moves to top if already present, adds if new
   */
  const touchAlbum = useCallback((albumId: number, albumTitle: string, artist: string) => {
    setRecentAlbums(prev => {
      // Remove existing entry for this album (if any)
      const filtered = prev.filter(entry => entry.albumId !== albumId);

      // Add new entry at the beginning
      const newEntry: RecentlyTouchedEntry = {
        albumId,
        albumTitle,
        artist,
        touchedAt: Date.now(),
      };

      // Limit to MAX_RECENT entries
      const updated = [newEntry, ...filtered].slice(0, MAX_RECENT);

      // Persist to localStorage
      saveRecentlyTouched(updated);

      return updated;
    });
  }, []);

  /**
   * Clear all recently touched albums
   */
  const clearRecent = useCallback(() => {
    setRecentAlbums([]);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return {
    recentAlbums,
    touchAlbum,
    clearRecent,
  };
}

export type { RecentlyTouchedEntry };
