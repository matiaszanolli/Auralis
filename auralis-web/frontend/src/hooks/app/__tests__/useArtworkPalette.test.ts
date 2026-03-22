import { renderHook, waitFor } from '@testing-library/react';
import { useArtworkPalette } from '../useArtworkPalette';
import type { ArtworkPalette } from '@/utils/colorExtraction';

vi.mock('@/utils/colorExtraction', () => ({
  extractArtworkColors: vi.fn(),
  generateArtworkGradient: vi.fn(),
  generateArtworkGlow: vi.fn(),
}));

import {
  extractArtworkColors,
  generateArtworkGradient,
  generateArtworkGlow,
} from '@/utils/colorExtraction';

const mockExtract = vi.mocked(extractArtworkColors);
const mockGradient = vi.mocked(generateArtworkGradient);
const mockGlow = vi.mocked(generateArtworkGlow);

const fakePalette: ArtworkPalette = {
  dominant: {
    r: 30,
    g: 30,
    b: 60,
    hex: '#1e1e3c',
    lightness: 18,
    saturation: 33,
    isVibrant: false,
    isDark: true,
    population: 100,
  },
  vibrant: {
    r: 115,
    g: 102,
    b: 240,
    hex: '#7366f0',
    lightness: 67,
    saturation: 82,
    isVibrant: true,
    isDark: false,
    population: 50,
  },
  isDarkArtwork: true,
};

describe('useArtworkPalette', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clear the module-level paletteCache between tests by re-importing would be
    // complex, so we just use unique albumIds per test to avoid cache hits.
    mockGradient.mockReturnValue('linear-gradient(#1e1e3c, #000)');
    mockGlow.mockReturnValue('0 0 40px rgba(115,102,240,0.15)');
  });

  it('returns null palette and no loading when enabled=false', () => {
    const { result } = renderHook(() => useArtworkPalette(42, false));

    expect(result.current.palette).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.gradient).toBe('transparent');
    expect(result.current.glow).toBe('none');
    expect(mockExtract).not.toHaveBeenCalled();
  });

  it('extracts colors and returns palette when enabled with valid albumId', async () => {
    mockExtract.mockResolvedValue(fakePalette);

    const { result } = renderHook(() => useArtworkPalette(101));

    // Should start loading
    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockExtract).toHaveBeenCalledWith('/api/albums/101/artwork', {
      colorCount: 5,
      sampleRate: 10,
      vibrantThreshold: 40,
    });
    expect(result.current.palette).toEqual(fakePalette);
    expect(result.current.error).toBeNull();
    expect(result.current.accentColor).toBe('#7366f0');
    expect(mockGradient).toHaveBeenCalledWith(fakePalette, 0.08);
    expect(mockGlow).toHaveBeenCalledWith(fakePalette, 0.15);
    expect(result.current.gradient).toBe('linear-gradient(#1e1e3c, #000)');
    expect(result.current.glow).toBe('0 0 40px rgba(115,102,240,0.15)');
  });

  it('sets error state when extraction fails', async () => {
    mockExtract.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useArtworkPalette(202));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.palette).toBeNull();
    expect(result.current.error).toBe('Network error');
    expect(result.current.gradient).toBe('transparent');
    expect(result.current.glow).toBe('none');
  });

  it('does not attempt extraction when albumId is undefined', () => {
    const { result } = renderHook(() => useArtworkPalette(undefined));

    expect(result.current.palette).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(mockExtract).not.toHaveBeenCalled();
  });
});
