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

/**
 * In-memory cache for artwork palettes
 * Key: albumId, Value: extracted palette
 */
const paletteCache = new Map<number, ArtworkPalette>();

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
    const cached = paletteCache.get(albumId);
    if (cached) {
      setPalette(cached);
      setLoading(false);
      setError(null);
      return;
    }

    // Extract colors from artwork
    const extractColors = async () => {
      setLoading(true);
      setError(null);

      try {
        const artworkUrl = `/api/albums/${albumId}/artwork`;
        const extractedPalette = await extractArtworkColors(artworkUrl, {
          colorCount: 5,
          sampleRate: 10,
          vibrantThreshold: 40,
        });

        // Check if this is still the current album (prevent race condition)
        if (currentAlbumIdRef.current === albumId) {
          setPalette(extractedPalette);
          paletteCache.set(albumId, extractedPalette);
          setLoading(false);
        }
      } catch (err) {
        // Check if this is still the current album
        if (currentAlbumIdRef.current === albumId) {
          console.warn(`[useArtworkPalette] Failed to extract colors for album ${albumId}:`, err);
          setError(err instanceof Error ? err.message : 'Failed to extract colors');
          setLoading(false);
        }
      }
    };

    extractColors();
  }, [albumId, enabled]);

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
