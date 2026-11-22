/**
 * extractArtworkColors end to end over a stubbed image + canvas (#6702):
 * sampling, clustering, ranking and the brand fallback.
 */

import { afterEach, describe, it, expect, vi } from 'vitest';
import { extractArtworkColors } from '@/utils/colorExtraction';
import { tokens } from '@/design-system/tokens';

const SIZE = 100;

/** RGBA data for a SIZE x SIZE canvas: `split` of the pixels one color, the rest another. */
function imageData(first: number[], second: number[], split: number): Uint8ClampedArray {
  const data = new Uint8ClampedArray(SIZE * SIZE * 4);
  for (let p = 0; p < SIZE * SIZE; p++) {
    data.set(p < SIZE * SIZE * split ? first : second, p * 4);
  }
  return data;
}

function stubCanvasAndImage(data: Uint8ClampedArray): void {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    drawImage: vi.fn(),
    getImageData: () => ({ data }),
  } as unknown as CanvasRenderingContext2D);

  class LoadingImage {
    crossOrigin = '';
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    set src(_url: string) {
      queueMicrotask(() => this.onload?.());
    }
  }
  vi.stubGlobal('Image', LoadingImage);
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('extractArtworkColors', () => {
  it('ranks the most populous color dominant and finds the vibrant one', async () => {
    // 70% dull dark grey-blue, 30% saturated red.
    stubCanvasAndImage(imageData([40, 40, 60, 255], [230, 20, 20, 255], 0.7));

    const palette = await extractArtworkColors('art.jpg', { colorCount: 2, sampleRate: 1 });

    expect(palette.dominant.hex.toLowerCase()).toBe('#28283c');
    expect(palette.vibrant?.hex.toLowerCase()).toBe('#e61414');
    expect(palette.accent?.hex.toLowerCase()).toBe('#e61414');
    expect(palette.isDarkArtwork).toBe(true);
  });

  it('falls back to the brand accent when every pixel is transparent', async () => {
    stubCanvasAndImage(imageData([200, 10, 10, 0], [200, 10, 10, 0], 1));

    const palette = await extractArtworkColors('blank.png');

    expect(palette.dominant.hex).toBe(tokens.colors.accent.primary);
    expect(palette.isDarkArtwork).toBe(false);
  });

  it('rejects when no 2D context is available', async () => {
    stubCanvasAndImage(new Uint8ClampedArray(0));
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);

    await expect(extractArtworkColors('art.jpg')).rejects.toThrow('Failed to get canvas context');
  });
});
