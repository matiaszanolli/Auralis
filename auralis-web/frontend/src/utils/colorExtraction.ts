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

/**
 * RGB color representation
 */
export interface RGBColor {
  r: number;
  g: number;
  b: number;
}

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
 * Convert RGB to Hex
 */
function rgbToHex(r: number, g: number, b: number): string {
  const toHex = (n: number) => {
    const hex = Math.round(n).toString(16);
    return hex.length === 1 ? '0' + hex : hex;
  };
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

/**
 * Convert RGB to HSL
 * Returns [hue (0-360), saturation (0-100), lightness (0-100)]
 */
function rgbToHsl(r: number, g: number, b: number): [number, number, number] {
  r /= 255;
  g /= 255;
  b /= 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const diff = max - min;

  let h = 0;
  let s = 0;
  const l = (max + min) / 2;

  if (diff !== 0) {
    s = l > 0.5 ? diff / (2 - max - min) : diff / (max + min);

    switch (max) {
      case r:
        h = ((g - b) / diff + (g < b ? 6 : 0)) / 6;
        break;
      case g:
        h = ((b - r) / diff + 2) / 6;
        break;
      case b:
        h = ((r - g) / diff + 4) / 6;
        break;
    }
  }

  return [h * 360, s * 100, l * 100];
}

/**
 * Calculate color distance (Euclidean in RGB space)
 */
function colorDistance(c1: RGBColor, c2: RGBColor): number {
  const dr = c1.r - c2.r;
  const dg = c1.g - c2.g;
  const db = c1.b - c2.b;
  return Math.sqrt(dr * dr + dg * dg + db * db);
}

/**
 * K-means clustering for color quantization
 * Groups similar colors together to find dominant colors
 */
function kMeansClustering(
  pixels: RGBColor[],
  k: number,
  maxIterations: number = 10
): { color: RGBColor; population: number }[] {
  if (pixels.length === 0) return [];
  if (k >= pixels.length) {
    // Not enough pixels for clustering, return unique colors
    const colorMap = new Map<string, { color: RGBColor; population: number }>();
    pixels.forEach((p) => {
      const key = `${p.r},${p.g},${p.b}`;
      const existing = colorMap.get(key);
      if (existing) {
        existing.population++;
      } else {
        colorMap.set(key, { color: p, population: 1 });
      }
    });
    return Array.from(colorMap.values())
      .sort((a, b) => b.population - a.population)
      .slice(0, k);
  }

  // Initialize centroids with k-means++ algorithm (better initial placement)
  const centroids: RGBColor[] = [];
  centroids.push(pixels[Math.floor(Math.random() * pixels.length)]);

  while (centroids.length < k) {
    const distances = pixels.map((p) =>
      Math.min(...centroids.map((c) => colorDistance(p, c)))
    );
    const totalDistance = distances.reduce((sum, d) => sum + d * d, 0);
    let threshold = Math.random() * totalDistance;

    for (let i = 0; i < pixels.length; i++) {
      threshold -= distances[i] * distances[i];
      if (threshold <= 0) {
        centroids.push(pixels[i]);
        break;
      }
    }
  }

  // Iterate k-means
  for (let iter = 0; iter < maxIterations; iter++) {
    // Assign pixels to nearest centroid
    const clusters: RGBColor[][] = Array.from({ length: k }, () => []);
    pixels.forEach((p) => {
      let minDist = Infinity;
      let minIdx = 0;
      centroids.forEach((c, i) => {
        const dist = colorDistance(p, c);
        if (dist < minDist) {
          minDist = dist;
          minIdx = i;
        }
      });
      clusters[minIdx].push(p);
    });

    // Update centroids (average of cluster)
    let changed = false;
    centroids.forEach((c, i) => {
      if (clusters[i].length === 0) return;
      const avgR = clusters[i].reduce((sum, p) => sum + p.r, 0) / clusters[i].length;
      const avgG = clusters[i].reduce((sum, p) => sum + p.g, 0) / clusters[i].length;
      const avgB = clusters[i].reduce((sum, p) => sum + p.b, 0) / clusters[i].length;

      if (Math.abs(c.r - avgR) > 1 || Math.abs(c.g - avgG) > 1 || Math.abs(c.b - avgB) > 1) {
        changed = true;
      }

      c.r = avgR;
      c.g = avgG;
      c.b = avgB;
    });

    if (!changed) break; // Converged early
  }

  // Return centroids with population counts
  return centroids.map((c, i) => ({
    color: { r: Math.round(c.r), g: Math.round(c.g), b: Math.round(c.b) },
    population: pixels.filter((p) => {
      let minIdx = 0;
      let minDist = Infinity;
      centroids.forEach((centroid, idx) => {
        const dist = colorDistance(p, centroid);
        if (dist < minDist) {
          minDist = dist;
          minIdx = idx;
        }
      });
      return minIdx === i;
    }).length,
  }));
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
          // Fallback to default palette if no valid pixels
          const defaultColor: ExtractedColor = {
            r: 115,
            g: 102,
            b: 240,
            hex: '#7366f0',
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
          const [h, s, l] = rgbToHsl(r, g, b);
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
