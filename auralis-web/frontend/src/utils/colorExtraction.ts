/**
 * Color Extraction Utility - Phase 4: Album View Emotional Anchor
 *
 * Extracts dominant colors from album artwork to create artwork-based theming.
 * Uses Canvas API for pixel sampling and k-means clustering for color quantization.
 *
 * Features:
 * - Dominant color extraction (1-3 colors)
 * - Vibrant vs. muted color detection
 * - Lightness/darkness calculation for contrast
 * - Color harmony generation (complementary, analogous)
 *
 * Design: "Let the music's visual identity flow into the UI"
 */

// Imported from the token module rather than the '@/design-system' barrel so a
// plain utility doesn't pull the component library in with it.
import { tokens, hexToRgb } from '@/design-system/tokens';
import { kMeansClustering } from './kMeans';
import { rgbToHex, rgbToHsl, type RGBColor } from './colorSpace';

export type { RGBColor };


/**
 * Extended color with metadata
 */
export interface ExtractedColor extends RGBColor {
  /** Hex representation (#RRGGBB) */
  hex: string;
  /** Lightness (0-100, HSL) */
  lightness: number;
  /** Saturation (0-100, HSL) */
  saturation: number;
  /** Is this color vibrant? (high saturation) */
  isVibrant: boolean;
  /** Is this color dark? (low lightness) */
  isDark: boolean;
  /** Percentage of pixels with this color */
  population: number;
}

/**
 * Album artwork color palette
 */
export interface ArtworkPalette {
  /** Primary dominant color (most prominent) */
  dominant: ExtractedColor;
  /** Secondary color (if available) */
  accent?: ExtractedColor;
  /** Vibrant color (if available) */
  vibrant?: ExtractedColor;
  /** Muted color (if available) */
  muted?: ExtractedColor;
  /** Is the overall artwork dark? */
  isDarkArtwork: boolean;
}

/**
 * RGB channels of the brand accent, derived from the token rather than
 * transcribed (#4463). `hexToRgb` returns null only for non-hex input, which a
 * literal token hex never is — the fallback keeps the type non-nullable.
 */
const BRAND_FALLBACK_RGB = hexToRgb(tokens.colors.accent.primary) ?? { r: 115, g: 102, b: 240 };


/**
 * Extract dominant colors from an image URL
 *
 * @param imageUrl - URL of the image to analyze
 * @param options - Extraction options
 * @returns Promise resolving to artwork color palette
 */
export async function extractArtworkColors(
  imageUrl: string,
  options: {
    /** Number of dominant colors to extract (default: 5) */
    colorCount?: number;
    /** Sample every Nth pixel for performance (default: 10) */
    sampleRate?: number;
    /** Minimum saturation to be considered vibrant (0-100, default: 40) */
    vibrantThreshold?: number;
  } = {}
): Promise<ArtworkPalette> {
  const {
    colorCount = 5,
    sampleRate = 10,
    vibrantThreshold = 40,
  } = options;

  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'Anonymous'; // Enable CORS for cross-origin images

    img.onload = () => {
      try {
        // Create canvas and draw image
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          reject(new Error('Failed to get canvas context'));
          return;
        }

        // Resize image to 100x100 for faster processing
        const size = 100;
        canvas.width = size;
        canvas.height = size;
        ctx.drawImage(img, 0, 0, size, size);

        // Extract pixel data
        const imageData = ctx.getImageData(0, 0, size, size);
        const pixels: RGBColor[] = [];

        // Sample pixels (every Nth pixel for performance)
        for (let i = 0; i < imageData.data.length; i += 4 * sampleRate) {
          const r = imageData.data[i];
          const g = imageData.data[i + 1];
          const b = imageData.data[i + 2];
          const a = imageData.data[i + 3];

          // Skip transparent pixels and very dark/light pixels (likely background)
          if (a < 128) continue;
          const brightness = (r + g + b) / 3;
          if (brightness < 10 || brightness > 245) continue;

          pixels.push({ r, g, b });
        }

        if (pixels.length === 0) {
          // Fallback to the brand accent. Was a hand-written copy of its hex
          // and channel numbers, which would silently drift on a rebrand (#4463).
          const defaultColor: ExtractedColor = {
            ...BRAND_FALLBACK_RGB,
            hex: tokens.colors.accent.primary,
            lightness: 67,
            saturation: 82,
            isVibrant: true,
            isDark: false,
            population: 100,
          };
          resolve({
            dominant: defaultColor,
            accent: defaultColor,
            vibrant: defaultColor,
            isDarkArtwork: false,
          });
          return;
        }

        // Use k-means clustering to find dominant colors
        const clusters = kMeansClustering(pixels, colorCount);

        // Sort by population (most dominant first)
        clusters.sort((a, b) => b.population - a.population);

        // Convert to ExtractedColor format
        const extractedColors: ExtractedColor[] = clusters.map((cluster) => {
          const { r, g, b } = cluster.color;
          const [_h, s, l] = rgbToHsl(r, g, b);
          return {
            r,
            g,
            b,
            hex: rgbToHex(r, g, b),
            lightness: l,
            saturation: s,
            isVibrant: s > vibrantThreshold,
            isDark: l < 50,
            population: cluster.population,
          };
        });

        // Determine if artwork is overall dark
        const avgLightness =
          extractedColors.reduce((sum, c) => sum + c.lightness * c.population, 0) /
          extractedColors.reduce((sum, c) => sum + c.population, 0);
        const isDarkArtwork = avgLightness < 50;

        // Find dominant, vibrant, and muted colors
        const dominant = extractedColors[0]; // Most populous color
        const vibrant = extractedColors.find((c) => c.isVibrant) || dominant;
        const muted = extractedColors.find((c) => !c.isVibrant) || extractedColors[1];
        const accent = extractedColors[1] || dominant; // Second most populous

        resolve({
          dominant,
          accent,
          vibrant,
          muted,
          isDarkArtwork,
        });
      } catch (err) {
        reject(err);
      }
    };

    img.onerror = () => {
      reject(new Error(`Failed to load image: ${imageUrl}`));
    };

    img.src = imageUrl;
  });
}

/**
 * Generate CSS background gradient from artwork palette
 *
 * @param palette - Extracted color palette
 * @param opacity - Gradient opacity (0-1, default: 0.1)
 * @returns CSS linear-gradient string
 */
export function generateArtworkGradient(
  palette: ArtworkPalette,
  opacity: number = 0.1
): string {
  const color1 = palette.dominant;
  const color2 = palette.accent || palette.dominant;

  const rgba1 = `rgba(${color1.r}, ${color1.g}, ${color1.b}, ${opacity})`;
  const rgba2 = `rgba(${color2.r}, ${color2.g}, ${color2.b}, ${opacity * 0.5})`;

  return `linear-gradient(135deg, ${rgba1} 0%, ${rgba2} 100%)`;
}

/**
 * Generate CSS glow/shadow from vibrant color
 *
 * @param palette - Extracted color palette
 * @param intensity - Glow intensity (0-1, default: 0.3)
 * @returns CSS box-shadow string
 */
export function generateArtworkGlow(
  palette: ArtworkPalette,
  intensity: number = 0.3
): string {
  const color = palette.vibrant || palette.dominant;
  const rgba = `rgba(${color.r}, ${color.g}, ${color.b}, ${intensity})`;

  return `0 8px 32px ${rgba}, 0 0 64px ${rgba}`;
}

export default {
  extractArtworkColors,
  generateArtworkGradient,
  generateArtworkGlow,
};
