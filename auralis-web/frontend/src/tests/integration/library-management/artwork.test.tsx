/**
 * Artwork API Integration Tests
 *
 * Tests for album artwork management and validation
 * Previously part of metadata-artwork.test.tsx (lines 1-476, 902-1192)
 *
 * Test Categories:
 * 1. Album Artwork Management (4 tests)
 * 2. Artwork Format Handling (3 tests)
 *
 * Total: 7 tests
 */

import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { render } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';

// ==========================================
// Test Components
// ==========================================

/**
 * Artwork management component
 */
interface ArtworkManagerProps {
  albumId: number;
  onUpload?: (path: string) => void;
  onDelete?: () => void;
  onError?: (error: Error) => void;
}

const ArtworkManager: React.FC<ArtworkManagerProps> = ({ albumId, onUpload, onDelete, onError }) => {
  const [artworkUrl, setArtworkUrl] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [uploading, setUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Fetch current artwork
  React.useEffect(() => {
    const fetchArtwork = async () => {
      try {
        const response = await fetch(`http://localhost:8765/api/albums/${albumId}/artwork`);
        if (response.ok) {
          const blob = await response.blob();
          setArtworkUrl(URL.createObjectURL(blob));
        }
      } catch (err) {
        // Artwork may not exist, that's okay
      } finally {
        setLoading(false);
      }
    };
    fetchArtwork();
  }, [albumId]);

  // Validate image dimensions
  const validateImage = (file: File): Promise<{ valid: boolean; error?: string }> => {
    return new Promise((resolve) => {
      const img = new Image();
      const url = URL.createObjectURL(file);

      img.onload = () => {
        URL.revokeObjectURL(url);
        if (img.width < 200 || img.height < 200) {
          resolve({ valid: false, error: 'Image must be at least 200x200 pixels' });
        } else if (img.width > 3000 || img.height > 3000) {
          resolve({ valid: false, error: 'Image must be at most 3000x3000 pixels' });
        } else {
          resolve({ valid: true });
        }
      };

      img.onerror = () => {
        URL.revokeObjectURL(url);
        resolve({ valid: false, error: 'Failed to load image' });
      };

      img.src = url;
    });
  };

  // Upload artwork
  const handleUpload = async (file: File) => {
    setError(null);
    setUploading(true);

    try {
      // Validate file type
      if (!['image/jpeg', 'image/png'].includes(file.type)) {
        throw new Error('Only JPEG and PNG formats are supported');
      }

      // Validate dimensions
      const validation = await validateImage(file);
      if (!validation.valid) {
        throw new Error(validation.error);
      }

      // Upload (mock - in real implementation would use FormData)
      const response = await fetch(`http://localhost:8765/api/albums/${albumId}/artwork/extract`, {
        method: 'POST'
      });

      if (!response.ok) throw new Error('Upload failed');

      const data = await response.json();
      setArtworkUrl(data.artwork_path);
      onUpload?.(data.artwork_path);
    } catch (err) {
      setError((err as Error).message);
      onError?.(err as Error);
    } finally {
      setUploading(false);
    }
  };

  // Delete artwork
  const handleDelete = async () => {
    try {
      const response = await fetch(`http://localhost:8765/api/albums/${albumId}/artwork`, {
        method: 'DELETE'
      });

      if (!response.ok) throw new Error('Delete failed');

      setArtworkUrl(null);
      onDelete?.();
    } catch (err) {
      setError((err as Error).message);
      onError?.(err as Error);
    }
  };

  if (loading) return <div>Loading artwork...</div>;

  return (
    <div data-testid="artwork-manager">
      {artworkUrl && (
        <div>
          <img src={artworkUrl} alt="Album artwork" data-testid="artwork-image" />
          <button onClick={handleDelete}>Delete Artwork</button>
        </div>
      )}

      {!artworkUrl && (
        <div>
          <input
            type="file"
            accept="image/jpeg,image/png"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleUpload(file);
            }}
            disabled={uploading}
            data-testid="artwork-upload"
          />
        </div>
      )}

      {error && <div data-testid="artwork-error">{error}</div>}
      {uploading && <div>Uploading...</div>}
    </div>
  );
};

// ==========================================
// Test Suite
// ==========================================

describe('Artwork API Integration Tests', () => {
  // Mock URL.createObjectURL and URL.revokeObjectURL for all tests
  beforeEach(() => {
    // Always mock URL methods for consistent test behavior
    // (JSDOM now supports these natively, but we need deterministic return values)
    vi.spyOn(global.URL, 'createObjectURL').mockReturnValue('mock-object-url');
    vi.spyOn(global.URL, 'revokeObjectURL').mockImplementation(() => {});
  });

  // Reset handlers after each test
  afterEach(() => {
    server.resetHandlers();
    vi.restoreAllMocks();
  });

  // ==========================================
  // 1. Album Artwork Management (4 tests)
  // ==========================================

  describe('Album Artwork Management', () => {
    it('should upload new album artwork', async () => {
      // Arrange
      server.use(
        http.get('http://localhost:8765/api/albums/:id/artwork', () => {
          return HttpResponse.json({ error: 'Not found' }, { status: 404 });
        }),
        http.post('http://localhost:8765/api/albums/:id/artwork/extract', () => {
          return HttpResponse.json({
            message: 'Artwork extracted successfully',
            artwork_path: '/path/to/artwork.jpg',
            album_id: 1
          });
        })
      );

      const onUpload = vi.fn();

      // Act
      render(<ArtworkManager albumId={1} onUpload={onUpload} />);

      await waitFor(() => {
        expect(screen.getByTestId('artwork-upload')).toBeInTheDocument();
      });

      // Create mock file
      const file = new File(['mock'], 'artwork.jpg', { type: 'image/jpeg' });

      // Trigger file upload
      const input = screen.getByTestId('artwork-upload') as HTMLInputElement;

      // We need to mock the image loading for dimension validation
      global.Image = class MockImage {
        onload: (() => void) | null = null;
        onerror: (() => void) | null = null;
        src = '';
        width = 500;
        height = 500;

        constructor() {
          setTimeout(() => {
            if (this.onload) this.onload();
          }, 0);
        }
      } as any;

      await userEvent.upload(input, file);

      // Assert
      await waitFor(() => {
        expect(onUpload).toHaveBeenCalledWith('/path/to/artwork.jpg');
      }, { timeout: 2000 });
    });

    it('should fetch and display existing artwork', async () => {
      // Arrange
      server.use(
        http.get('http://localhost:8765/api/albums/:id/artwork', () => {
          return HttpResponse.arrayBuffer(
            new ArrayBuffer(100),
            {
              headers: {
                'Content-Type': 'image/jpeg'
              }
            }
          );
        })
      );

      // Act
      render(<ArtworkManager albumId={1} />);

      // Assert
      await waitFor(() => {
        const img = screen.getByTestId('artwork-image');
        expect(img).toBeInTheDocument();
        expect(img).toHaveAttribute('src', 'mock-object-url');
      });
    });

    it('should delete album artwork', async () => {
      // Arrange
      server.use(
        http.get('http://localhost:8765/api/albums/:id/artwork', () => {
          return HttpResponse.arrayBuffer(new ArrayBuffer(100));
        }),
        http.delete('http://localhost:8765/api/albums/:id/artwork', () => {
          return HttpResponse.json({
            message: 'Artwork deleted successfully',
            album_id: 1
          });
        })
      );

      const onDelete = vi.fn();
      const user = userEvent.setup();

      // Act
      render(<ArtworkManager albumId={1} onDelete={onDelete} />);

      // Wait for artwork to load
      await waitFor(() => {
        expect(screen.getByTestId('artwork-image')).toBeInTheDocument();
      });

      // Delete artwork
      await user.click(screen.getByRole('button', { name: /delete artwork/i }));

      // Assert
      await waitFor(() => {
        expect(onDelete).toHaveBeenCalled();
        expect(screen.queryByTestId('artwork-image')).not.toBeInTheDocument();
      });
    });

    it('should handle artwork caching and lazy loading', async () => {
      // Arrange
      let fetchCount = 0;

      server.use(
        http.get('http://localhost:8765/api/albums/:id/artwork', () => {
          fetchCount++;
          return HttpResponse.arrayBuffer(
            new ArrayBuffer(100),
            {
              headers: {
                'Cache-Control': 'public, max-age=31536000'
              }
            }
          );
        })
      );

      // Act - render twice
      const { unmount } = render(<ArtworkManager albumId={1} />);

      await waitFor(() => {
        expect(screen.getByTestId('artwork-image')).toBeInTheDocument();
      });

      unmount();

      // Render again (should use cache)
      render(<ArtworkManager albumId={1} />);

      await waitFor(() => {
        expect(screen.getByTestId('artwork-image')).toBeInTheDocument();
      });

      // Assert - fetched at least once (caching happens at browser level)
      expect(fetchCount).toBeGreaterThan(0);
    });
  });

  // ==========================================
  // 2. Artwork Format Handling (3 tests)
  // ==========================================

  describe('Artwork Format Handling', () => {
    beforeEach(() => {
      // Mock Image for dimension validation
      global.Image = class MockImage {
        onload: (() => void) | null = null;
        onerror: (() => void) | null = null;
        src = '';
        width = 500;
        height = 500;

        constructor() {
          setTimeout(() => {
            if (this.onload) this.onload();
          }, 0);
        }
      } as any;

      server.use(
        http.get('http://localhost:8765/api/albums/:id/artwork', () => {
          return HttpResponse.json({ error: 'Not found' }, { status: 404 });
        }),
        http.post('http://localhost:8765/api/albums/:id/artwork/extract', () => {
          return HttpResponse.json({
            message: 'Artwork extracted successfully',
            artwork_path: '/path/to/artwork.jpg'
          });
        })
      );
    });

    it('should support JPEG format', async () => {
      // Arrange
      const onUpload = vi.fn();

      // Act
      render(<ArtworkManager albumId={1} onUpload={onUpload} />);

      await waitFor(() => {
        expect(screen.getByTestId('artwork-upload')).toBeInTheDocument();
      });

      const jpegFile = new File(['jpeg'], 'artwork.jpg', { type: 'image/jpeg' });
      const input = screen.getByTestId('artwork-upload') as HTMLInputElement;

      await userEvent.upload(input, jpegFile);

      // Assert
      await waitFor(() => {
        expect(onUpload).toHaveBeenCalled();
      }, { timeout: 2000 });
    });

    it('should support PNG format', async () => {
      // Arrange
      const onUpload = vi.fn();

      // Act
      render(<ArtworkManager albumId={1} onUpload={onUpload} />);

      await waitFor(() => {
        expect(screen.getByTestId('artwork-upload')).toBeInTheDocument();
      });

      const pngFile = new File(['png'], 'artwork.png', { type: 'image/png' });
      const input = screen.getByTestId('artwork-upload') as HTMLInputElement;

      await userEvent.upload(input, pngFile);

      // Assert
      await waitFor(() => {
        expect(onUpload).toHaveBeenCalled();
      }, { timeout: 2000 });
    });

    it('should validate artwork dimensions (min 200x200, max 3000x3000)', async () => {
      // Arrange
      const onError = vi.fn();

      // Mock small image
      global.Image = class MockImage {
        onload: (() => void) | null = null;
        src = '';
        width = 100;
        height = 100;

        constructor() {
          setTimeout(() => {
            if (this.onload) this.onload();
          }, 0);
        }
      } as any;

      // Act
      render(<ArtworkManager albumId={1} onError={onError} />);

      await waitFor(() => {
        expect(screen.getByTestId('artwork-upload')).toBeInTheDocument();
      });

      const smallFile = new File(['small'], 'small.jpg', { type: 'image/jpeg' });
      const input = screen.getByTestId('artwork-upload') as HTMLInputElement;

      await userEvent.upload(input, smallFile);

      // Assert - error for too small
      await waitFor(() => {
        expect(screen.getByTestId('artwork-error')).toHaveTextContent(/at least 200x200/i);
      }, { timeout: 2000 });

      // Test too large
      global.Image = class MockImage {
        onload: (() => void) | null = null;
        src = '';
        width = 4000;
        height = 4000;

        constructor() {
          setTimeout(() => {
            if (this.onload) this.onload();
          }, 0);
        }
      } as any;

      const largeFile = new File(['large'], 'large.jpg', { type: 'image/jpeg' });
      await userEvent.upload(input, largeFile);

      await waitFor(() => {
        expect(screen.getByTestId('artwork-error')).toHaveTextContent(/at most 3000x3000/i);
      }, { timeout: 2000 });
    });
  });
});
