/**
 * TrackRowAlbumArt Component Tests
 *
 * Tests for album art thumbnail in track row:
 * - Image display with albumArt URL
 * - Fallback icon when image unavailable
 * - Image error handling
 * - Conditional rendering based on shouldShowImage
 */

import { vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { TrackRowAlbumArt } from '../TrackRowAlbumArt';

describe('TrackRowAlbumArt', () => {
  const mockOnImageError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Image Display', () => {
    it('should display image when shouldShowImage is true and albumArt is provided', () => {
      render(
        <TrackRowAlbumArt
          albumArt="https://example.com/album-art.jpg"
          title="Test Track"
          album="Test Album"
          shouldShowImage={true}
          onImageError={mockOnImageError}
        />
      );

      const image = screen.getByAltText('Test Album');
      expect(image).toBeInTheDocument();
      expect(image.getAttribute('src')).toBe('https://example.com/album-art.jpg');
    });

    it('should use title as alt text when album is not provided', () => {
      render(
        <TrackRowAlbumArt
          albumArt="https://example.com/album-art.jpg"
          title="Test Track"
          shouldShowImage={true}
          onImageError={mockOnImageError}
        />
      );

      const image = screen.getByAltText('Test Track');
      expect(image).toBeInTheDocument();
    });

    it('should display fallback icon when shouldShowImage is false', () => {
      const { container } = render(
        <TrackRowAlbumArt
          albumArt="https://example.com/album-art.jpg"
          title="Test Track"
          shouldShowImage={false}
          onImageError={mockOnImageError}
        />
      );

      // Should not have image
      expect(screen.queryByAltText('Test Track')).not.toBeInTheDocument();

      // Should have music note icon (SVG)
      expect(container.querySelector('svg')).toBeInTheDocument();
    });

    it('should display fallback icon when albumArt is not provided', () => {
      const { container } = render(
        <TrackRowAlbumArt
          title="Test Track"
          shouldShowImage={true}
          onImageError={mockOnImageError}
        />
      );

      expect(screen.queryByRole('img')).not.toBeInTheDocument();
      expect(container.querySelector('svg')).toBeInTheDocument();
    });

    it('should display fallback icon when both shouldShowImage is false and no albumArt', () => {
      const { container } = render(
        <TrackRowAlbumArt
          title="Test Track"
          shouldShowImage={false}
          onImageError={mockOnImageError}
        />
      );

      expect(screen.queryByRole('img')).not.toBeInTheDocument();
      expect(container.querySelector('svg')).toBeInTheDocument();
    });
  });

  describe('Image Error Handling', () => {
    it('should call onImageError when image fails to load', () => {
      render(
        <TrackRowAlbumArt
          albumArt="https://example.com/album-art.jpg"
          title="Test Track"
          shouldShowImage={true}
          onImageError={mockOnImageError}
        />
      );

      const image = screen.getByAltText('Test Track') as HTMLImageElement;

      // Simulate image load error
      const errorEvent = new Event('error');
      image.dispatchEvent(errorEvent);

      expect(mockOnImageError).toHaveBeenCalledTimes(1);
    });

    it('should not call onImageError when image is not shown', () => {
      render(
        <TrackRowAlbumArt
          albumArt="https://example.com/album-art.jpg"
          title="Test Track"
          shouldShowImage={false}
          onImageError={mockOnImageError}
        />
      );

      // Image is not rendered, so no error handler is attached
      expect(mockOnImageError).not.toHaveBeenCalled();
    });
  });

  describe('Conditional Rendering', () => {
    it('should toggle between image and icon based on shouldShowImage', () => {
      const { rerender } = render(
        <TrackRowAlbumArt
          albumArt="https://example.com/album-art.jpg"
          title="Test Track"
          shouldShowImage={true}
          onImageError={mockOnImageError}
        />
      );

      // Initially shows image
      expect(screen.getByAltText('Test Track')).toBeInTheDocument();

      // Rerender with shouldShowImage false
      rerender(
        <TrackRowAlbumArt
          albumArt="https://example.com/album-art.jpg"
          title="Test Track"
          shouldShowImage={false}
          onImageError={mockOnImageError}
        />
      );

      // Now shows icon instead
      expect(screen.queryByAltText('Test Track')).not.toBeInTheDocument();
    });

    it('should update image URL when albumArt prop changes', () => {
      const { rerender } = render(
        <TrackRowAlbumArt
          albumArt="https://example.com/album-art-1.jpg"
          title="Test Track"
          shouldShowImage={true}
          onImageError={mockOnImageError}
        />
      );

      let image = screen.getByAltText('Test Track') as HTMLImageElement;
      expect(image.src).toContain('album-art-1.jpg');

      // Update image URL
      rerender(
        <TrackRowAlbumArt
          albumArt="https://example.com/album-art-2.jpg"
          title="Test Track"
          shouldShowImage={true}
          onImageError={mockOnImageError}
        />
      );

      image = screen.getByAltText('Test Track') as HTMLImageElement;
      expect(image.src).toContain('album-art-2.jpg');
    });
  });

  describe('Metadata Props', () => {
    it('should handle optional album prop', () => {
      const { rerender } = render(
        <TrackRowAlbumArt
          albumArt="https://example.com/album-art.jpg"
          title="Test Track"
          shouldShowImage={true}
          onImageError={mockOnImageError}
        />
      );

      // When album is not provided, title is used as alt text
      expect(screen.getByAltText('Test Track')).toBeInTheDocument();

      // Rerender with album
      rerender(
        <TrackRowAlbumArt
          albumArt="https://example.com/album-art.jpg"
          title="Test Track"
          album="Test Album"
          shouldShowImage={true}
          onImageError={mockOnImageError}
        />
      );

      // Now album name is used as alt text
      expect(screen.getByAltText('Test Album')).toBeInTheDocument();
    });

    it('should handle special characters in title and album', () => {
      render(
        <TrackRowAlbumArt
          albumArt="https://example.com/album-art.jpg"
          title="Test Track & Artist's Song"
          album="Album (2024)"
          shouldShowImage={true}
          onImageError={mockOnImageError}
        />
      );

      const image = screen.getByAltText('Album (2024)');
      expect(image).toBeInTheDocument();
    });
  });

  describe('Image Properties', () => {
    it('should have correct image attributes', () => {
      render(
        <TrackRowAlbumArt
          albumArt="https://example.com/album-art.jpg"
          title="Test Track"
          album="Test Album"
          shouldShowImage={true}
          onImageError={mockOnImageError}
        />
      );

      const image = screen.getByAltText('Test Album') as HTMLImageElement;
      expect(image.src).toBe('https://example.com/album-art.jpg');
      expect(image.alt).toBe('Test Album');
    });
  });

  describe('Error Handler Integration', () => {
    it('should handle multiple image errors', () => {
      render(
        <TrackRowAlbumArt
          albumArt="https://example.com/album-art.jpg"
          title="Test Track"
          shouldShowImage={true}
          onImageError={mockOnImageError}
        />
      );

      const image = screen.getByAltText('Test Track') as HTMLImageElement;

      // Simulate multiple error events
      image.dispatchEvent(new Event('error'));
      image.dispatchEvent(new Event('error'));

      expect(mockOnImageError).toHaveBeenCalledTimes(2);
    });
  });
});
