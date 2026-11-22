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


/** Side of the square the artwork is downscaled to before sampling. */
const SAMPLE_SIZE = 100;

/**
 * Opaque, non-background pixels of *img*, every *sampleRate*-th one, after
 * downscaling to SAMPLE_SIZE square. Throws when no 2D canvas context exists.
 */
function sampleImagePixels(img: HTMLImageElement, sampleRate: number): RGBColor[] {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Failed to get canvas context');
  canvas.width = SAMPLE_SIZE;
  canvas.height = SAMPLE_SIZE;
  ctx.drawImage(img, 0, 0, SAMPLE_SIZE, SAMPLE_SIZE);

  const { data } = ctx.getImageData(0, 0, SAMPLE_SIZE, SAMPLE_SIZE);
  const pixels: RGBColor[] = [];
  for (let i = 0; i < data.length; i += 4 * sampleRate) {
    const [r, g, b, a] = [data[i], data[i + 1], data[i + 2], data[i + 3]];
    // Skip transparent pixels and very dark/light pixels (likely background)
    const brightness = (r + g + b) / 3;
    if (a < 128 || brightness < 10 || brightness > 245) continue;
    pixels.push({ r, g, b });
  }
  return pixels;
}

/**
 * The brand-accent palette used when no pixel survives sampling. Derived from
 * the token rather than a hand-written copy of its hex and channels, which
 * would silently drift on a rebrand (#4463).
 */
function brandFallbackPalette(): ArtworkPalette {
  const color: ExtractedColor = {
    ...BRAND_FALLBACK_RGB,
    hex: tokens.colors.accent.primary,
    lightness: 67,
    saturation: 82,
    isVibrant: true,
    isDark: false,
    population: 100,
  };
  return { dominant: color, accent: color, vibrant: color, isDarkArtwork: false };
}

function toExtractedColor(color: RGBColor, population: number, vibrantThreshold: number): ExtractedColor {
  const { r, g, b } = color;
  const [, s, l] = rgbToHsl(r, g, b);
  return {
    r, g, b,
    hex: rgbToHex(r, g, b),
    lightness: l,
    saturation: s,
    isVibrant: s > vibrantThreshold,
    isDark: l < 50,
    population,
  };
}

/** Pick the palette roles from colors sorted most populous first. */
function rankPalette(colors: ExtractedColor[]): ArtworkPalette {
  const totalPopulation = colors.reduce((sum, c) => sum + c.population, 0);
  const avgLightness = colors.reduce((sum, c) => sum + c.lightness * c.population, 0) / totalPopulation;
  const dominant = colors[0];
  return {
    dominant,
    accent: colors[1] || dominant,
    vibrant: colors.find((c) => c.isVibrant) || dominant,
    muted: colors.find((c) => !c.isVibrant) || colors[1],
    isDarkArtwork: avgLightness < 50,
  };
}

/** Sample, cluster (k-means) and rank one loaded image's colors. */
function paletteFromImage(
  img: HTMLImageElement,
  colorCount: number,
  sampleRate: number,
  vibrantThreshold: number
): ArtworkPalette {
  const pixels = sampleImagePixels(img, sampleRate);
  if (pixels.length === 0) return brandFallbackPalette();
  const clusters = kMeansClustering(pixels, colorCount).sort((a, b) => b.population - a.population);
  return rankPalette(clusters.map((c) => toExtractedColor(c.color, c.population, vibrantThreshold)));
}

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
  const { colorCount = 5, sampleRate = 10, vibrantThreshold = 40 } = options;

  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'Anonymous'; // Enable CORS for cross-origin images
    img.onload = () => {
      try {
        resolve(paletteFromImage(img, colorCount, sampleRate, vibrantThreshold));
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
