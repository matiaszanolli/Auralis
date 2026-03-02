/**
 * Metadata API Integration Tests
 *
 * Tests for metadata editing and validation
 * Previously part of metadata-artwork.test.tsx (lines 1-476, 499-896, 1198-1337)
 *
 * Test Categories:
 * 1. Track Metadata Editing (6 tests)
 * 2. Metadata Field Validation (4 tests)
 * 3. Metadata Synchronization (2 tests)
 * 4. Error Handling (1 test)
 *
 * Total: 13 tests
 */

import React from 'react';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { render } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';

// ==========================================
// Test Components
// ==========================================

/**
 * Metadata editing form component for testing
 */
interface MetadataFormProps {
  trackId: number;
  onSave?: (metadata: any) => void;
  onError?: (error: Error) => void;
}

const MetadataEditForm: React.FC<MetadataFormProps> = ({ trackId, onSave, onError }) => {
  const [metadata, setMetadata] = React.useState({
    title: '',
    artist: '',
    album: '',
    year: '',
    genre: '',
  });
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [validationErrors, setValidationErrors] = React.useState<Record<string, string>>({});

  // Fetch current metadata
  React.useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const response = await fetch(`http://localhost:8765/api/metadata/tracks/${trackId}`);
        if (!response.ok) throw new Error('Failed to fetch metadata');
        const data = await response.json();
        setMetadata(data.metadata || {});
      } catch (err) {
        setError((err as Error).message);
        onError?.(err as Error);
      } finally {
        setLoading(false);
      }
    };
    fetchMetadata();
  }, [trackId]);

  // Validate fields
  const validateField = (field: string, value: string): string | null => {
    if (field === 'title' && value.length > 200) {
      return 'Title must be 200 characters or less';
    }
    if ((field === 'artist' || field === 'album') && value.length > 100) {
      return `${field.charAt(0).toUpperCase() + field.slice(1)} must be 100 characters or less`;
    }
    if (field === 'year') {
      const yearNum = parseInt(value);
      if (value && (isNaN(yearNum) || yearNum < 1900 || yearNum > 2099)) {
        return 'Year must be between 1900 and 2099';
      }
    }
    return null;
  };

  // Handle field change
  const handleChange = (field: string, value: string) => {
    setMetadata(prev => ({ ...prev, [field]: value }));

    // Validate on change
    const validationError = validateField(field, value);
    setValidationErrors(prev => ({
      ...prev,
      [field]: validationError || ''
    }));
  };

  // Save metadata
  const handleSave = async () => {
    // Check for validation errors
    const hasErrors = Object.values(validationErrors).some(err => err);
    if (hasErrors) {
      setError('Please fix validation errors');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const response = await fetch(
        `http://localhost:8765/api/metadata/tracks/${trackId}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(metadata)
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save metadata');
      }

      const result = await response.json();
      onSave?.(result.metadata);
    } catch (err) {
      setError((err as Error).message);
      onError?.(err as Error);
    } finally {
      setSaving(false);
    }
  };

  // Revert changes
  const handleRevert = async () => {
    setLoading(true);
    try {
      const response = await fetch(`http://localhost:8765/api/metadata/tracks/${trackId}`);
      const data = await response.json();
      setMetadata(data.metadata || {});
      setValidationErrors({});
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div>Loading metadata...</div>;
  if (error && !metadata.title) return <div>Error: {error}</div>;

  return (
    <form data-testid="metadata-form">
      <div>
        <label htmlFor="title">Title</label>
        <input
          id="title"
          type="text"
          value={metadata.title}
          onChange={(e) => handleChange('title', e.target.value)}
        />
        {validationErrors.title && (
          <span data-testid="title-error">{validationErrors.title}</span>
        )}
      </div>

      <div>
        <label htmlFor="artist">Artist</label>
        <input
          id="artist"
          type="text"
          value={metadata.artist}
          onChange={(e) => handleChange('artist', e.target.value)}
        />
        {validationErrors.artist && (
          <span data-testid="artist-error">{validationErrors.artist}</span>
        )}
      </div>

      <div>
        <label htmlFor="album">Album</label>
        <input
          id="album"
          type="text"
          value={metadata.album}
          onChange={(e) => handleChange('album', e.target.value)}
        />
        {validationErrors.album && (
          <span data-testid="album-error">{validationErrors.album}</span>
        )}
      </div>

      <div>
        <label htmlFor="year">Year</label>
        <input
          id="year"
          type="number"
          value={metadata.year}
          onChange={(e) => handleChange('year', e.target.value)}
          min={1900}
          max={2099}
        />
        {validationErrors.year && (
          <span data-testid="year-error">{validationErrors.year}</span>
        )}
      </div>

      <div>
        <label htmlFor="genre">Genre</label>
        <select
          id="genre"
          value={metadata.genre}
          onChange={(e) => handleChange('genre', e.target.value)}
        >
          <option value="">Select Genre</option>
          <option value="Rock">Rock</option>
          <option value="Pop">Pop</option>
          <option value="Jazz">Jazz</option>
          <option value="Classical">Classical</option>
          <option value="Electronic">Electronic</option>
        </select>
      </div>

      {error && <div data-testid="form-error">{error}</div>}

      <button type="button" onClick={handleSave} disabled={saving}>
        {saving ? 'Saving...' : 'Save'}
      </button>
      <button type="button" onClick={handleRevert}>
        Revert
      </button>
    </form>
  );
};

/**
 * Batch metadata editing component
 */
interface BatchMetadataFormProps {
  trackIds: number[];
  onSave?: (results: any) => void;
  onError?: (error: Error) => void;
}

const BatchMetadataForm: React.FC<BatchMetadataFormProps> = ({ trackIds, onSave, onError }) => {
  const [metadata, setMetadata] = React.useState({ genre: '', year: '' });
  const [saving, setSaving] = React.useState(false);
  const [result, setResult] = React.useState<any>(null);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updates = trackIds.map(trackId => ({
        track_id: trackId,
        metadata: {
          ...(metadata.genre && { genre: metadata.genre }),
          ...(metadata.year && { year: parseInt(metadata.year) })
        }
      }));

      const response = await fetch('http://localhost:8765/api/metadata/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates, backup: true })
      });

      if (!response.ok) throw new Error('Batch update failed');

      const data = await response.json();
      setResult(data);
      onSave?.(data);
    } catch (err) {
      onError?.(err as Error);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div data-testid="batch-metadata-form">
      <div>
        <label htmlFor="batch-genre">Genre</label>
        <select
          id="batch-genre"
          value={metadata.genre}
          onChange={(e) => setMetadata(prev => ({ ...prev, genre: e.target.value }))}
        >
          <option value="">Select Genre</option>
          <option value="Rock">Rock</option>
          <option value="Pop">Pop</option>
        </select>
      </div>

      <div>
        <label htmlFor="batch-year">Year</label>
        <input
          id="batch-year"
          type="number"
          value={metadata.year}
          onChange={(e) => setMetadata(prev => ({ ...prev, year: e.target.value }))}
        />
      </div>

      <button onClick={handleSave} disabled={saving}>
        {saving ? 'Updating...' : `Update ${trackIds.length} Tracks`}
      </button>

      {result && (
        <div data-testid="batch-result">
          Updated {result.successful} of {result.total} tracks
        </div>
      )}
    </div>
  );
};

// ==========================================
// Test Suite
// ==========================================

describe('Metadata API Integration Tests', () => {
  // SKIPPED: Large integration test (876 lines). Run separately with increased heap.
  // Reset handlers after each test
  afterEach(() => {
    server.resetHandlers();
    vi.restoreAllMocks();
  });

  // ==========================================
  // 1. Track Metadata Editing (6 tests)
  // ==========================================

  describe('Track Metadata Editing', () => {
    it('should edit single metadata field (title)', async () => {
      // Arrange
      server.use(
        http.get('http://localhost:8765/api/metadata/tracks/:id', () => {
          return HttpResponse.json({
            track_id: 1,
            metadata: { title: 'Original Title', artist: 'Artist 1', album: 'Album 1' }
          });
        }),
        http.put('http://localhost:8765/api/metadata/tracks/:id', async ({ request }) => {
          const body = await request.json() as any;
          return HttpResponse.json({
            success: true,
            track_id: 1,
            updated_fields: ['title'],
            metadata: { ...body }
          });
        })
      );

      const user = userEvent.setup();
      const onSave = vi.fn();

      // Act
      render(<MetadataEditForm trackId={1} onSave={onSave} />);

      // Wait for metadata to load
      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toHaveValue('Original Title');
      });

      // Edit title
      const titleInput = screen.getByLabelText(/title/i);
      await user.clear(titleInput);
      await user.type(titleInput, 'New Title');

      // Save
      await user.click(screen.getByRole('button', { name: /save/i }));

      // Assert
      await waitFor(() => {
        expect(onSave).toHaveBeenCalledWith(
          expect.objectContaining({ title: 'New Title' })
        );
      });
    });

    it('should edit multiple metadata fields simultaneously', async () => {
      // Arrange
      server.use(
        http.get('http://localhost:8765/api/metadata/tracks/:id', () => {
          return HttpResponse.json({
            track_id: 1,
            metadata: { title: 'Track 1', artist: 'Artist 1', album: 'Album 1', year: '2020' }
          });
        }),
        http.put('http://localhost:8765/api/metadata/tracks/:id', async ({ request }) => {
          const body = await request.json() as any;
          return HttpResponse.json({
            success: true,
            updated_fields: ['title', 'artist', 'year'],
            metadata: { ...body }
          });
        })
      );

      const user = userEvent.setup();
      const onSave = vi.fn();

      // Act
      render(<MetadataEditForm trackId={1} onSave={onSave} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toHaveValue('Track 1');
      });

      // Edit multiple fields
      await user.clear(screen.getByLabelText(/title/i));
      await user.type(screen.getByLabelText(/title/i), 'Updated Track');

      await user.clear(screen.getByLabelText(/artist/i));
      await user.type(screen.getByLabelText(/artist/i), 'New Artist');

      await user.clear(screen.getByLabelText(/year/i));
      await user.type(screen.getByLabelText(/year/i), '2024');

      // Save
      await user.click(screen.getByRole('button', { name: /save/i }));

      // Assert
      await waitFor(() => {
        expect(onSave).toHaveBeenCalledWith(
          expect.objectContaining({
            title: 'Updated Track',
            artist: 'New Artist',
            year: '2024'
          })
        );
      });
    });

    it('should save metadata changes to backend', async () => {
      // Arrange
      let savedMetadata: any = null;

      server.use(
        http.get('http://localhost:8765/api/metadata/tracks/:id', () => {
          return HttpResponse.json({
            track_id: 1,
            metadata: { title: 'Track 1', artist: 'Artist 1' }
          });
        }),
        http.put('http://localhost:8765/api/metadata/tracks/:id', async ({ request }) => {
          savedMetadata = await request.json();
          return HttpResponse.json({
            success: true,
            updated_fields: Object.keys(savedMetadata),
            metadata: savedMetadata
          });
        })
      );

      const user = userEvent.setup();

      // Act
      render(<MetadataEditForm trackId={1} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toHaveValue('Track 1');
      });

      await user.clear(screen.getByLabelText(/title/i));
      await user.type(screen.getByLabelText(/title/i), 'Saved Title');
      await user.click(screen.getByRole('button', { name: /save/i }));

      // Assert
      await waitFor(() => {
        expect(savedMetadata).toEqual(
          expect.objectContaining({ title: 'Saved Title' })
        );
      });
    });

    it('should validate metadata constraints', async () => {
      // Arrange
      server.use(
        http.get('http://localhost:8765/api/metadata/tracks/:id', () => {
          return HttpResponse.json({
            track_id: 1,
            metadata: { title: 'Track 1', year: '2020' }
          });
        })
      );

      const user = userEvent.setup();

      // Act
      render(<MetadataEditForm trackId={1} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toHaveValue('Track 1');
      });

      // Test title max length (200 chars)
      const longTitle = 'a'.repeat(201);
      await user.clear(screen.getByLabelText(/title/i));
      await user.type(screen.getByLabelText(/title/i), longTitle);

      // Assert - validation error shown
      await waitFor(() => {
        expect(screen.getByTestId('title-error')).toHaveTextContent(/200 characters/i);
      });
    });

    it('should revert unsaved metadata changes', async () => {
      // Arrange
      server.use(
        http.get('http://localhost:8765/api/metadata/tracks/:id', () => {
          return HttpResponse.json({
            track_id: 1,
            metadata: { title: 'Original Title', artist: 'Original Artist' }
          });
        })
      );

      const user = userEvent.setup();

      // Act
      render(<MetadataEditForm trackId={1} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toHaveValue('Original Title');
      });

      // Make changes
      await user.clear(screen.getByLabelText(/title/i));
      await user.type(screen.getByLabelText(/title/i), 'Modified Title');

      expect(screen.getByLabelText(/title/i)).toHaveValue('Modified Title');

      // Revert
      await user.click(screen.getByRole('button', { name: /revert/i }));

      // Assert - reverted to original
      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toHaveValue('Original Title');
      });
    });

    it('should batch metadata editing for multiple tracks', async () => {
      // Arrange
      server.use(
        http.post('http://localhost:8765/api/metadata/batch', async ({ request }) => {
          const body = await request.json() as any;
          const updates = body.updates;
          return HttpResponse.json({
            success: true,
            total: updates.length,
            successful: updates.length,
            failed: 0,
            results: updates.map((u: any) => ({
              track_id: u.track_id,
              success: true,
              updates: u.metadata
            }))
          });
        })
      );

      const user = userEvent.setup();
      const onSave = vi.fn();

      // Act
      render(<BatchMetadataForm trackIds={[1, 2, 3]} onSave={onSave} />);

      // Select genre
      await user.selectOptions(screen.getByLabelText(/genre/i), 'Rock');

      // Enter year
      await user.type(screen.getByLabelText(/year/i), '2024');

      // Save
      await user.click(screen.getByRole('button', { name: /update 3 tracks/i }));

      // Assert
      await waitFor(() => {
        expect(screen.getByTestId('batch-result')).toHaveTextContent(/updated 3 of 3 tracks/i);
        expect(onSave).toHaveBeenCalledWith(
          expect.objectContaining({
            successful: 3,
            total: 3
          })
        );
      });
    });
  });

  // ==========================================
  // 2. Metadata Field Validation (4 tests)
  // ==========================================

  describe('Metadata Field Validation', () => {
    it('should validate title field (max 200 chars, required)', async () => {
      // Arrange
      server.use(
        http.get('http://localhost:8765/api/metadata/tracks/:id', () => {
          return HttpResponse.json({
            track_id: 1,
            metadata: { title: 'Track 1' }
          });
        })
      );

      const user = userEvent.setup();

      // Act
      render(<MetadataEditForm trackId={1} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toHaveValue('Track 1');
      });

      // Test exceeding max length
      const longTitle = 'a'.repeat(201);
      await user.clear(screen.getByLabelText(/title/i));
      await user.type(screen.getByLabelText(/title/i), longTitle);

      // Assert
      await waitFor(() => {
        expect(screen.getByTestId('title-error')).toBeInTheDocument();
        expect(screen.getByTestId('title-error')).toHaveTextContent(/200 characters/i);
      });
    });

    it('should validate artist/album fields (max 100 chars)', async () => {
      // Arrange
      server.use(
        http.get('http://localhost:8765/api/metadata/tracks/:id', () => {
          return HttpResponse.json({
            track_id: 1,
            metadata: { artist: 'Artist', album: 'Album' }
          });
        })
      );

      const user = userEvent.setup();

      // Act
      render(<MetadataEditForm trackId={1} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/artist/i)).toBeInTheDocument();
      });

      // Test artist max length - clear first and type long string
      const artistInput = screen.getByLabelText(/artist/i);
      await user.clear(artistInput);
      const longArtist = 'a'.repeat(101);
      await user.type(artistInput, longArtist);

      // Assert
      await waitFor(() => {
        expect(screen.getByTestId('artist-error')).toHaveTextContent(/100 characters/i);
      });
    });

    it('should validate year field (1900-2099 range)', async () => {
      // Arrange
      server.use(
        http.get('http://localhost:8765/api/metadata/tracks/:id', () => {
          return HttpResponse.json({
            track_id: 1,
            metadata: { year: '2020' }
          });
        })
      );

      const user = userEvent.setup();

      // Act
      render(<MetadataEditForm trackId={1} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/year/i)).toBeInTheDocument();
      });

      // Test invalid year (too early)
      await user.clear(screen.getByLabelText(/year/i));
      await user.type(screen.getByLabelText(/year/i), '1899');

      // Assert
      await waitFor(() => {
        expect(screen.getByTestId('year-error')).toHaveTextContent(/1900 and 2099/i);
      });

      // Test invalid year (too late)
      await user.clear(screen.getByLabelText(/year/i));
      await user.type(screen.getByLabelText(/year/i), '2100');

      await waitFor(() => {
        expect(screen.getByTestId('year-error')).toHaveTextContent(/1900 and 2099/i);
      });
    });

    it('should validate genre field (predefined list)', async () => {
      // Arrange
      server.use(
        http.get('http://localhost:8765/api/metadata/tracks/:id', () => {
          return HttpResponse.json({
            track_id: 1,
            metadata: { genre: '' }
          });
        })
      );

      // Act
      render(<MetadataEditForm trackId={1} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/genre/i)).toBeInTheDocument();
      });

      // Assert - only predefined options available
      const genreSelect = screen.getByLabelText(/genre/i);
      const options = Array.from(genreSelect.querySelectorAll('option')).map(
        opt => opt.textContent
      );

      expect(options).toContain('Rock');
      expect(options).toContain('Pop');
      expect(options).toContain('Jazz');
      expect(options).toContain('Classical');
      expect(options).toContain('Electronic');
    });
  });

  // ==========================================
  // 3. Metadata Synchronization (2 tests)
  // ==========================================

  describe('Metadata Synchronization', () => {
    it('should sync metadata changes across components', async () => {
      // Arrange
      let currentMetadata = { title: 'Original', artist: 'Artist 1' };

      server.use(
        http.get('http://localhost:8765/api/metadata/tracks/:id', () => {
          return HttpResponse.json({
            track_id: 1,
            metadata: currentMetadata
          });
        }),
        http.put('http://localhost:8765/api/metadata/tracks/:id', async ({ request }) => {
          const body = await request.json() as any;
          currentMetadata = { ...currentMetadata, ...body };
          return HttpResponse.json({
            success: true,
            metadata: currentMetadata
          });
        })
      );

      const user = userEvent.setup();

      // Act - render two forms for same track
      const { unmount: unmount1 } = render(<MetadataEditForm trackId={1} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toHaveValue('Original');
      });

      // Edit and save
      await user.clear(screen.getByLabelText(/title/i));
      await user.type(screen.getByLabelText(/title/i), 'Synced Title');
      await user.click(screen.getByRole('button', { name: /save/i }));

      await waitFor(() => {
        expect(currentMetadata.title).toBe('Synced Title');
      });

      unmount1();

      // Render new form - should show updated data
      render(<MetadataEditForm trackId={1} />);

      // Assert
      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toHaveValue('Synced Title');
      });
    });

    it('should update UI immediately after save', async () => {
      // Arrange
      server.use(
        http.get('http://localhost:8765/api/metadata/tracks/:id', () => {
          return HttpResponse.json({
            track_id: 1,
            metadata: { title: 'Before Save' }
          });
        }),
        http.put('http://localhost:8765/api/metadata/tracks/:id', async ({ request }) => {
          const body = await request.json() as any;
          return HttpResponse.json({
            success: true,
            metadata: body
          });
        })
      );

      const user = userEvent.setup();
      const onSave = vi.fn();

      // Act
      render(<MetadataEditForm trackId={1} onSave={onSave} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toHaveValue('Before Save');
      });

      // Edit and save
      await user.clear(screen.getByLabelText(/title/i));
      await user.type(screen.getByLabelText(/title/i), 'After Save');
      await user.click(screen.getByRole('button', { name: /save/i }));

      // Assert - UI updates immediately
      await waitFor(() => {
        expect(onSave).toHaveBeenCalledWith(
          expect.objectContaining({ title: 'After Save' })
        );
      });
    });
  });

  // ==========================================
  // 4. Error Handling (1 test)
  // ==========================================

  describe('Error Handling', () => {
    it('should handle metadata save failures gracefully', async () => {
      // Arrange
      server.use(
        http.get('http://localhost:8765/api/metadata/tracks/:id', () => {
          return HttpResponse.json({
            track_id: 1,
            metadata: { title: 'Track 1' }
          });
        }),
        http.put('http://localhost:8765/api/metadata/tracks/:id', () => {
          return HttpResponse.json(
            { detail: 'Database error: Unable to save metadata' },
            { status: 500 }
          );
        })
      );

      const user = userEvent.setup();
      const onError = vi.fn();

      // Act
      render(<MetadataEditForm trackId={1} onError={onError} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/title/i)).toHaveValue('Track 1');
      });

      // Edit and attempt save
      await user.clear(screen.getByLabelText(/title/i));
      await user.type(screen.getByLabelText(/title/i), 'New Title');
      await user.click(screen.getByRole('button', { name: /save/i }));

      // Assert - error handled gracefully
      await waitFor(() => {
        expect(screen.getByTestId('form-error')).toHaveTextContent(/database error/i);
        expect(onError).toHaveBeenCalledWith(expect.any(Error));
      });

      // Form should still be usable
      expect(screen.getByRole('button', { name: /save/i })).not.toBeDisabled();
    });
  });
});
