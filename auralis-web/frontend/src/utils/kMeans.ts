/**
 * K-means colour quantization for artwork palettes.
 *
 * Split out of colorExtraction.ts (#5841).
 */

import { colorDistance, type RGBColor } from './colorSpace';

/**
 * K-means clustering for color quantization
 * Groups similar colors together to find dominant colors
 */
export function kMeansClustering(
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
