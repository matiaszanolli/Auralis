import { renderHook, waitFor, act } from '@testing-library/react';
import { useArtworkPalette, _internal as artworkPaletteInternal } from '../useArtworkPalette';
import type { ArtworkPalette } from '@/utils/colorExtraction';
import { tokens } from '@/design-system/tokens';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { _internal as artworkUpdatesInternal } from '@/hooks/library/useArtworkUpdates';

vi.mock('@/utils/colorExtraction', () => ({
  extractArtworkColors: vi.fn(),
  generateArtworkGradient: vi.fn(),
  generateArtworkGlow: vi.fn(),
}));
vi.mock('@/contexts/WebSocketContext');

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
  let capturedArtworkUpdate: ((message: unknown) => void) | null;

  beforeEach(() => {
    vi.clearAllMocks();
    artworkUpdatesInternal.reset();
    capturedArtworkUpdate = null;
    const subscribe = vi.fn((_type: string, handler: (message: unknown) => void) => {
      capturedArtworkUpdate = handler;
      return vi.fn();
    });
    vi.mocked(useWebSocketContext).mockReturnValue({ subscribe } as never);
    // Belt-and-suspenders: explicitly clear the module-level paletteCache
    // between tests (via _internal.reset(), #5020) in addition to using
    // unique albumIds per test to avoid cache hits.
    artworkPaletteInternal.reset();
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

    // Colour extraction requests a small thumbnail variant, not the full-res
    // bitmap (#4447).
    expect(mockExtract).toHaveBeenCalledWith('/api/albums/101/artwork?size=64', {
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

  it('re-extracts and caches a distinct palette after artwork_updated (#4530)', async () => {
    const revisedPalette: ArtworkPalette = {
      ...fakePalette,
      vibrant: { ...fakePalette.vibrant, hex: '#ff5500' },
    };
    mockExtract
      .mockResolvedValueOnce(fakePalette)
      .mockResolvedValueOnce(revisedPalette);

    const { result } = renderHook(() => useArtworkPalette(303));
    await waitFor(() => expect(result.current.palette).toEqual(fakePalette));

    act(() => {
      capturedArtworkUpdate?.({ type: 'artwork_updated', data: { album_id: 303 } });
    });

    await waitFor(() => expect(result.current.palette).toEqual(revisedPalette));
    expect(mockExtract).toHaveBeenNthCalledWith(
      2,
      '/api/albums/303/artwork?size=64&v=1',
      expect.any(Object)
    );
  });

  it('clears the old palette when revised artwork cannot be extracted (#4530)', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    mockExtract
      .mockResolvedValueOnce(fakePalette)
      .mockRejectedValueOnce(new Error('Artwork deleted'));

    const { result } = renderHook(() => useArtworkPalette(404));
    await waitFor(() => expect(result.current.palette).toEqual(fakePalette));

    act(() => {
      capturedArtworkUpdate?.({
        type: 'artwork_updated',
        data: { album_id: 404, action: 'deleted' },
      });
    });

    await waitFor(() => expect(result.current.error).toBe('Artwork deleted'));
    expect(result.current.palette).toBeNull();
    // #4463: the no-palette fallback is the brand token, not a transcribed hex.
    expect(result.current.accentColor).toBe(tokens.colors.accent.primary);
  });

  it('does not invalidate another album palette on unrelated updates (#4530)', async () => {
    mockExtract.mockResolvedValue(fakePalette);
    const { result } = renderHook(() => useArtworkPalette(505));
    await waitFor(() => expect(result.current.palette).toEqual(fakePalette));

    act(() => {
      capturedArtworkUpdate?.({ type: 'artwork_updated', data: { album_id: 999 } });
    });

    expect(mockExtract).toHaveBeenCalledOnce();
    expect(result.current.palette).toEqual(fakePalette);
  });

  it('does not attempt extraction when albumId is undefined', () => {
    const { result } = renderHook(() => useArtworkPalette(undefined));

    expect(result.current.palette).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(mockExtract).not.toHaveBeenCalled();
  });

  it('caps paletteCache at maxEntries, evicting the least-recently-used entry (#5020)', async () => {
    mockExtract.mockResolvedValue(fakePalette);
    const { maxEntries, cache } = artworkPaletteInternal;

    // Fill the cache to its cap.
    for (let albumId = 1; albumId <= maxEntries; albumId++) {
      const { result, unmount } = renderHook(() => useArtworkPalette(albumId));
      await waitFor(() => expect(result.current.loading).toBe(false));
      unmount();
    }
    expect(cache.size).toBe(maxEntries);
    expect(cache.has(1)).toBe(true);

    // One more distinct album pushes the cache past its cap.
    const { result, unmount } = renderHook(() => useArtworkPalette(maxEntries + 1));
    await waitFor(() => expect(result.current.loading).toBe(false));
    unmount();

    expect(cache.size).toBe(maxEntries);
    expect(cache.has(1)).toBe(false); // oldest (least-recently-used) evicted
    expect(cache.has(maxEntries + 1)).toBe(true);
  });
});
