/**
 * useNavigationState Hook Tests
 *
 * Tests for library view navigation state:
 * - Album and artist selection
 * - Back navigation handlers
 * - View change behavior
 */

import { vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useNavigationState } from '../useNavigationState';

describe('useNavigationState', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Hook Initialization', () => {
    it('should initialize with null selection states', () => {
      const { result } = renderHook(() => useNavigationState({ view: 'library' }));

      expect(result.current.selectedAlbumId).toBeNull();
      expect(result.current.selectedArtistId).toBeNull();
      expect(result.current.selectedArtistName).toBe('');
    });
  });

  describe('View Change Reset', () => {
    it('should reset all states when view prop changes', () => {
      const { result, rerender } = renderHook(
        ({ view }) => useNavigationState({ view }),
        {
          initialProps: { view: 'library' },
        }
      );

      // Set some state
      act(() => {
        result.current.handleAlbumClick(1);
        result.current.handleArtistClick(10, 'Artist Name');
      });

      expect(result.current.selectedAlbumId).toBe(1);
      expect(result.current.selectedArtistId).toBe(10);
      expect(result.current.selectedArtistName).toBe('Artist Name');

      // Change view
      rerender({ view: 'favorites' });

      expect(result.current.selectedAlbumId).toBeNull();
      expect(result.current.selectedArtistId).toBeNull();
      expect(result.current.selectedArtistName).toBe('');
    });
  });

  describe('handleBackFromAlbum', () => {
    it('should clear selectedAlbumId', () => {
      const { result } = renderHook(() => useNavigationState({ view: 'library' }));

      act(() => {
        result.current.handleAlbumClick(1);
      });

      expect(result.current.selectedAlbumId).toBe(1);

      act(() => {
        result.current.handleBackFromAlbum();
      });

      expect(result.current.selectedAlbumId).toBeNull();
    });

    it('should preserve selectedArtistId when going back from album', () => {
      const { result } = renderHook(() => useNavigationState({ view: 'library' }));

      act(() => {
        result.current.handleArtistClick(10, 'Artist Name');
        result.current.handleAlbumClick(1);
      });

      expect(result.current.selectedAlbumId).toBe(1);
      expect(result.current.selectedArtistId).toBe(10);

      act(() => {
        result.current.handleBackFromAlbum();
      });

      expect(result.current.selectedAlbumId).toBeNull();
      expect(result.current.selectedArtistId).toBe(10);
      expect(result.current.selectedArtistName).toBe('Artist Name');
    });
  });

  describe('handleBackFromArtist', () => {
    it('should clear both artist states', () => {
      const { result } = renderHook(() => useNavigationState({ view: 'library' }));

      act(() => {
        result.current.handleArtistClick(10, 'Artist Name');
      });

      expect(result.current.selectedArtistId).toBe(10);
      expect(result.current.selectedArtistName).toBe('Artist Name');

      act(() => {
        result.current.handleBackFromArtist();
      });

      expect(result.current.selectedArtistId).toBeNull();
      expect(result.current.selectedArtistName).toBe('');
    });

    it('should not affect selectedAlbumId', () => {
      const { result } = renderHook(() => useNavigationState({ view: 'library' }));

      act(() => {
        result.current.handleAlbumClick(1);
        result.current.handleArtistClick(10, 'Artist Name');
      });

      expect(result.current.selectedAlbumId).toBe(1);
      expect(result.current.selectedArtistId).toBe(10);

      act(() => {
        result.current.handleBackFromArtist();
      });

      expect(result.current.selectedAlbumId).toBe(1);
      expect(result.current.selectedArtistId).toBeNull();
      expect(result.current.selectedArtistName).toBe('');
    });
  });

  describe('handleAlbumClick', () => {
    it('should set selectedAlbumId', () => {
      const { result } = renderHook(() => useNavigationState({ view: 'library' }));

      expect(result.current.selectedAlbumId).toBeNull();

      act(() => {
        result.current.handleAlbumClick(42);
      });

      expect(result.current.selectedAlbumId).toBe(42);
    });

    it('should update selectedAlbumId on multiple clicks', () => {
      const { result } = renderHook(() => useNavigationState({ view: 'library' }));

      act(() => {
        result.current.handleAlbumClick(1);
      });

      expect(result.current.selectedAlbumId).toBe(1);

      act(() => {
        result.current.handleAlbumClick(2);
      });

      expect(result.current.selectedAlbumId).toBe(2);
    });
  });

  describe('handleArtistClick', () => {
    it('should set selectedArtistId and selectedArtistName', () => {
      const { result } = renderHook(() => useNavigationState({ view: 'library' }));

      act(() => {
        result.current.handleArtistClick(10, 'Taylor Swift');
      });

      expect(result.current.selectedArtistId).toBe(10);
      expect(result.current.selectedArtistName).toBe('Taylor Swift');
    });

    it('should update both artist fields', () => {
      const { result } = renderHook(() => useNavigationState({ view: 'library' }));

      act(() => {
        result.current.handleArtistClick(1, 'Artist 1');
      });

      expect(result.current.selectedArtistId).toBe(1);
      expect(result.current.selectedArtistName).toBe('Artist 1');

      act(() => {
        result.current.handleArtistClick(2, 'Artist 2');
      });

      expect(result.current.selectedArtistId).toBe(2);
      expect(result.current.selectedArtistName).toBe('Artist 2');
    });
  });

  describe('State Transitions', () => {
    it('should handle album click then artist click correctly', () => {
      const { result } = renderHook(() => useNavigationState({ view: 'library' }));

      // Click album
      act(() => {
        result.current.handleAlbumClick(1);
      });

      expect(result.current.selectedAlbumId).toBe(1);
      expect(result.current.selectedArtistId).toBeNull();

      // Then click artist
      act(() => {
        result.current.handleArtistClick(10, 'Artist');
      });

      expect(result.current.selectedAlbumId).toBe(1);
      expect(result.current.selectedArtistId).toBe(10);
      expect(result.current.selectedArtistName).toBe('Artist');
    });

    it('should handle back navigation flow', () => {
      const { result } = renderHook(() => useNavigationState({ view: 'library' }));

      // Start in library, click artist
      act(() => {
        result.current.handleArtistClick(10, 'Artist');
      });

      expect(result.current.selectedArtistId).toBe(10);

      // Click album in artist detail
      act(() => {
        result.current.handleAlbumClick(1);
      });

      expect(result.current.selectedAlbumId).toBe(1);
      expect(result.current.selectedArtistId).toBe(10);

      // Go back from album (stay in artist)
      act(() => {
        result.current.handleBackFromAlbum();
      });

      expect(result.current.selectedAlbumId).toBeNull();
      expect(result.current.selectedArtistId).toBe(10);

      // Go back from artist (return to library)
      act(() => {
        result.current.handleBackFromArtist();
      });

      expect(result.current.selectedAlbumId).toBeNull();
      expect(result.current.selectedArtistId).toBeNull();
    });
  });

  describe('Handler Memoization', () => {
    it('should memoize all handlers', () => {
      const { result, rerender } = renderHook(() =>
        useNavigationState({ view: 'library' })
      );

      const initialHandlers = {
        back_album: result.current.handleBackFromAlbum,
        back_artist: result.current.handleBackFromArtist,
        album_click: result.current.handleAlbumClick,
        artist_click: result.current.handleArtistClick,
      };

      rerender();

      expect(result.current.handleBackFromAlbum).toBe(initialHandlers.back_album);
      expect(result.current.handleBackFromArtist).toBe(initialHandlers.back_artist);
      expect(result.current.handleAlbumClick).toBe(initialHandlers.album_click);
      expect(result.current.handleArtistClick).toBe(initialHandlers.artist_click);
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty artist name', () => {
      const { result } = renderHook(() => useNavigationState({ view: 'library' }));

      act(() => {
        result.current.handleArtistClick(10, '');
      });

      expect(result.current.selectedArtistId).toBe(10);
      expect(result.current.selectedArtistName).toBe('');
    });

    it('should handle back when nothing is selected', () => {
      const { result } = renderHook(() => useNavigationState({ view: 'library' }));

      // Should not throw
      expect(() => {
        act(() => {
          result.current.handleBackFromAlbum();
          result.current.handleBackFromArtist();
        });
      }).not.toThrow();

      expect(result.current.selectedAlbumId).toBeNull();
      expect(result.current.selectedArtistId).toBeNull();
    });

    it('should handle rapid navigation changes', () => {
      const { result } = renderHook(() => useNavigationState({ view: 'library' }));

      act(() => {
        result.current.handleAlbumClick(1);
        result.current.handleAlbumClick(2);
        result.current.handleAlbumClick(3);
        result.current.handleArtistClick(10, 'Artist');
        result.current.handleArtistClick(20, 'Another Artist');
      });

      expect(result.current.selectedAlbumId).toBe(3);
      expect(result.current.selectedArtistId).toBe(20);
      expect(result.current.selectedArtistName).toBe('Another Artist');
    });
  });
});
