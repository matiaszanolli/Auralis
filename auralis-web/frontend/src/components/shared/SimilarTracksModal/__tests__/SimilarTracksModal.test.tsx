import { render, screen, fireEvent } from '@/test/test-utils';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { SimilarTracksModal } from '../SimilarTracksModal';

// Mock the fingerprint hooks module
const mockFindSimilar = vi.fn().mockResolvedValue([]);
const mockClear = vi.fn();
const mockUseSimilarTracks = vi.fn(() => ({
  similarTracks: null,
  loading: false,
  error: null,
  findSimilar: mockFindSimilar,
  clear: mockClear,
}));

vi.mock('@/hooks/fingerprint', () => ({
  useSimilarTracks: (...args: unknown[]) => mockUseSimilarTracks(...args),
}));

const defaultProps = {
  open: true,
  trackId: 42 as number | null,
  trackTitle: 'Test Song',
  onClose: vi.fn(),
  onTrackPlay: vi.fn(),
};

const sampleTracks = [
  { trackId: 10, distance: 0.1, similarityScore: 0.92, title: 'Similar A', artist: 'Artist A' },
  { trackId: 20, distance: 0.3, similarityScore: 0.78, title: 'Similar B', artist: 'Artist B' },
];

describe('SimilarTracksModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSimilarTracks.mockReturnValue({
      similarTracks: null,
      loading: false,
      error: null,
      findSimilar: mockFindSimilar,
      clear: mockClear,
    });
  });

  it('does not render content when open=false', () => {
    render(<SimilarTracksModal {...defaultProps} open={false} />);

    expect(screen.queryByText('Similar Tracks')).not.toBeInTheDocument();
  });

  it('calls findSimilar(trackId, { limit, includeDetails: true }) when open and trackId is set', () => {
    render(<SimilarTracksModal {...defaultProps} trackId={42} limit={15} />);

    expect(mockFindSimilar).toHaveBeenCalledWith(42, { limit: 15, includeDetails: true });
  });

  it('uses default limit of 20 when not specified', () => {
    render(<SimilarTracksModal {...defaultProps} trackId={7} />);

    expect(mockFindSimilar).toHaveBeenCalledWith(7, { limit: 20, includeDetails: true });
  });

  it('does not call findSimilar when trackId is null', () => {
    render(<SimilarTracksModal {...defaultProps} trackId={null} />);

    expect(mockFindSimilar).not.toHaveBeenCalled();
  });

  it('shows loading state with CircularProgress when loading=true', () => {
    mockUseSimilarTracks.mockReturnValue({
      similarTracks: null,
      loading: true,
      error: null,
      findSimilar: mockFindSimilar,
      clear: mockClear,
    });

    render(<SimilarTracksModal {...defaultProps} />);

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.getByText('Analyzing fingerprint space...')).toBeInTheDocument();
  });

  it('shows error message when error is set', () => {
    mockUseSimilarTracks.mockReturnValue({
      similarTracks: null,
      loading: false,
      error: 'Connection failed',
      findSimilar: mockFindSimilar,
      clear: mockClear,
    });

    render(<SimilarTracksModal {...defaultProps} />);

    expect(screen.getByText(/Connection failed/)).toBeInTheDocument();
    expect(screen.getByText('Try again or select a different track.')).toBeInTheDocument();
  });

  it('shows "No similar tracks found" when similarTracks is empty', () => {
    mockUseSimilarTracks.mockReturnValue({
      similarTracks: [],
      loading: false,
      error: null,
      findSimilar: mockFindSimilar,
      clear: mockClear,
    });

    render(<SimilarTracksModal {...defaultProps} />);

    expect(screen.getByText('No similar tracks found.')).toBeInTheDocument();
  });

  it('renders track list with titles, artists, and similarity scores', () => {
    mockUseSimilarTracks.mockReturnValue({
      similarTracks: sampleTracks,
      loading: false,
      error: null,
      findSimilar: mockFindSimilar,
      clear: mockClear,
    });

    render(<SimilarTracksModal {...defaultProps} />);

    expect(screen.getByText('Similar A')).toBeInTheDocument();
    expect(screen.getByText('Artist A')).toBeInTheDocument();
    expect(screen.getByText('92% match')).toBeInTheDocument();

    expect(screen.getByText('Similar B')).toBeInTheDocument();
    expect(screen.getByText('Artist B')).toBeInTheDocument();
    expect(screen.getByText('78% match')).toBeInTheDocument();
  });

  it('calls onTrackPlay and onClose when clicking a track', () => {
    mockUseSimilarTracks.mockReturnValue({
      similarTracks: sampleTracks,
      loading: false,
      error: null,
      findSimilar: mockFindSimilar,
      clear: mockClear,
    });

    render(<SimilarTracksModal {...defaultProps} />);

    fireEvent.click(screen.getByText('Similar A'));

    expect(defaultProps.onTrackPlay).toHaveBeenCalledWith(10);
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it('calls clear() when modal closes (open transitions to false)', () => {
    const { rerender } = render(<SimilarTracksModal {...defaultProps} open={true} />);

    mockClear.mockClear();

    rerender(<SimilarTracksModal {...defaultProps} open={false} />);

    expect(mockClear).toHaveBeenCalled();
  });

  it('displays track title in subtitle', () => {
    render(<SimilarTracksModal {...defaultProps} trackTitle="My Great Song" />);

    expect(screen.getByText(/Tracks similar to "My Great Song"/)).toBeInTheDocument();
  });
});
