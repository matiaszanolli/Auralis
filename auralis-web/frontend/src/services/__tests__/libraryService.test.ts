import { getArtistTracks } from '../libraryService';

// Mock the apiRequest utility
vi.mock('@/utils/apiRequest', () => ({
  get: vi.fn(),
}));

import { get } from '@/utils/apiRequest';

const mockGet = vi.mocked(get);

describe('libraryService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getArtistTracks', () => {
    it('fetches artist tracks with correct endpoint', async () => {
      const mockResponse = {
        id: 42,
        name: 'Test Artist',
        tracks: [{ id: 1, title: 'Song A', album: 'Album', album_id: 1, duration: 200 }],
        total_tracks: 1,
      };
      mockGet.mockResolvedValue(mockResponse);

      const result = await getArtistTracks(42);

      expect(mockGet).toHaveBeenCalledOnce();
      expect(mockGet).toHaveBeenCalledWith(
        expect.stringContaining('/42'),
        expect.any(Object)
      );
      expect(result).toEqual(mockResponse);
    });

    it('passes abort signal to get()', async () => {
      mockGet.mockResolvedValue({ id: 1, name: 'A', tracks: [], total_tracks: 0 });
      const controller = new AbortController();

      await getArtistTracks(1, controller.signal);

      expect(mockGet).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ signal: controller.signal })
      );
    });

    it('propagates errors from get()', async () => {
      mockGet.mockRejectedValue(new Error('Network error'));

      await expect(getArtistTracks(99)).rejects.toThrow('Network error');
    });
  });
});
