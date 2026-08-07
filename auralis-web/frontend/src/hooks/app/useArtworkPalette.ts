/**
 * useArtworkPalette Hook - Phase 4: Album View Emotional Anchor
 *
 * Manages artwork color extraction and caching for album theming.
 * Extracts dominant colors from album artwork and provides CSS values for theming.
 *
 * Features:
 * - Async color extraction from artwork URL
 * - In-memory caching by album ID
 * - Loading and error states
 * - Pre-generated CSS gradient and glow values
 *
 * Usage:
 * ```tsx
 * const { palette, loading, gradient, glow } = useArtworkPalette(albumId);
 * <div style={{ background: gradient }} />
 * ```
 */

import { useState, useEffect, useRef } from 'react';
import {
  extractArtworkColors,
  generateArtworkGradient,
  generateArtworkGlow,
  type ArtworkPalette,
} from '@/utils/colorExtraction';
import { getArtworkUrl } from '@/services/artworkService';
import { useArtworkRevision } from '@/hooks/library/useArtworkUpdates';

/**
 * In-memory cache for artwork palettes
 * Each album retains only the palette for its current artwork revision.
 *
 * Bounded with LRU eviction (#5020) — entries were previously only ever
 * added or replaced, never removed for albums no longer displayed. A `Map`
 * preserves insertion order, so re-inserting an entry on every access moves
 * it to the end; the oldest (first) key is evicted once the cap is exceeded.
 */
const MAX_PALETTE_CACHE_ENTRIES = 500;
const paletteCache = new Map<number, { revision: number; palette: ArtworkPalette }>();

function getCachedPalette(
  albumId: number
): { revision: number; palette: ArtworkPalette } | undefined {
  const entry = paletteCache.get(albumId);
  if (entry) {
    paletteCache.delete(albumId);
    paletteCache.set(albumId, entry);
  }
  return entry;
}

function setCachedPalette(albumId: number, revision: number, palette: ArtworkPalette): void {
  paletteCache.delete(albumId);
  paletteCache.set(albumId, { revision, palette });
  if (paletteCache.size > MAX_PALETTE_CACHE_ENTRIES) {
    const oldestKey = paletteCache.keys().next().value;
    if (oldestKey !== undefined) {
      paletteCache.delete(oldestKey);
    }
  }
}

/**
 * Hook return type
 */
interface UseArtworkPaletteReturn {
  /** Extracted color palette (null if loading or error) */
  palette: ArtworkPalette | null;
  /** Is extraction in progress? */
  loading: boolean;
  /** Error message (if extraction failed) */
  error: string | null;
  /** Pre-generated CSS background gradient */
  gradient: string;
  /** Pre-generated CSS box-shadow glow */
  glow: string;
  /** Accent color hex (for borders, accents) */
  accentColor: string;
}

/**
 * useArtworkPalette Hook
 *
 * Extracts dominant colors from album artwork for theming.
 * Caches results in memory to avoid redundant extractions.
 *
 * @param albumId - Album ID to extract colors from
 * @param enabled - Enable color extraction (default: true)
 * @returns Artwork palette and CSS theming values
 */
export function useArtworkPalette(
  albumId: number | null | undefined,
  enabled: boolean = true
): UseArtworkPaletteReturn {
  const artworkRevision = useArtworkRevision(albumId ?? 0);
  const [palette, setPalette] = useState<ArtworkPalette | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Track current album ID to prevent race conditions
  const currentAlbumIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled || !albumId) {
      setPalette(null);
      setLoading(false);
      setError(null);
      return;
    }

    currentAlbumIdRef.current = albumId;

    // Check cache first
    const cached = getCachedPalette(albumId);
    if (cached?.revision === artworkRevision) {
      setPalette(cached.palette);
      setLoading(false);
      setError(null);
      return;
    }

    // #3590: track unmount with an isActive flag so we don't setState on a
    // dead component if extractArtworkColors resolves after navigation.
    // The album-change guard via currentAlbumIdRef does not cover unmount.
    let isActive = true;

    const extractColors = async () => {
      // Do not keep displaying the previous revision's colours while a new
      // image loads or after artwork deletion makes extraction fail (#4530).
      setPalette(null);
      setLoading(true);
      setError(null);

      try {
        // Colour extraction downsamples heavily, so a small thumbnail is more
        // than enough — never fetch the full-resolution bitmap for this (#4447).
        const artworkUrl = getArtworkUrl(albumId, { size: 64, revision: artworkRevision });
        const extractedPalette = await extractArtworkColors(artworkUrl, {
          colorCount: 5,
          sampleRate: 10,
          vibrantThreshold: 40,
        });

        if (!isActive) return;
        if (currentAlbumIdRef.current === albumId) {
          setPalette(extractedPalette);
          setCachedPalette(albumId, artworkRevision, extractedPalette);
          setLoading(false);
        }
      } catch (err) {
        if (!isActive) return;
        if (currentAlbumIdRef.current === albumId) {
          console.warn(`[useArtworkPalette] Failed to extract colors for album ${albumId}:`, err);
          setError(err instanceof Error ? err.message : 'Failed to extract colors');
          setLoading(false);
        }
      }
    };

    extractColors();

    return () => {
      isActive = false;
    };
  }, [albumId, enabled, artworkRevision]);

  // Generate CSS values from palette
  const gradient = palette ? generateArtworkGradient(palette, 0.08) : 'transparent';
  const glow = palette ? generateArtworkGlow(palette, 0.15) : 'none';
  const accentColor = palette?.vibrant?.hex || palette?.dominant?.hex || '#7366f0';

  return {
    palette,
    loading,
    error,
    gradient,
    glow,
    accentColor,
  };
}

export default useArtworkPalette;

// Test/debug helpers
export const _internal = {
  cache: paletteCache,
  maxEntries: MAX_PALETTE_CACHE_ENTRIES,
  reset() {
    paletteCache.clear();
  },
};
