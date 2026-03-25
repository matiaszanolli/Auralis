import { vi, describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@/test/test-utils';
import { ArtistInfoModal } from '../ArtistInfoModal';

const mockArtist = {
  id: 1,
  name: 'Pink Floyd',
  albumCount: 15,
  trackCount: 165,
};

describe('ArtistInfoModal', () => {
  it('renders nothing when artist is null', () => {
    const { container } = render(
      <ArtistInfoModal open={true} artist={null} onClose={vi.fn()} />
    );
    expect(container.innerHTML).toBe('');
  });

  it('displays artist name', () => {
    render(<ArtistInfoModal open={true} artist={mockArtist} onClose={vi.fn()} />);
    expect(screen.getByText('Pink Floyd')).toBeInTheDocument();
  });

  it('displays album and track counts', () => {
    render(<ArtistInfoModal open={true} artist={mockArtist} onClose={vi.fn()} />);
    expect(screen.getByText('15')).toBeInTheDocument();
    expect(screen.getByText('165')).toBeInTheDocument();
    expect(screen.getByText('Albums')).toBeInTheDocument();
    expect(screen.getByText('Tracks')).toBeInTheDocument();
  });

  it('defaults counts to 0 when undefined', () => {
    const artist = { id: 2, name: 'Unknown' } as any;
    render(<ArtistInfoModal open={true} artist={artist} onClose={vi.fn()} />);
    expect(screen.getAllByText('0')).toHaveLength(2);
  });

  it('calls onClose when Close button clicked', () => {
    const onClose = vi.fn();
    render(<ArtistInfoModal open={true} artist={mockArtist} onClose={onClose} />);
    fireEvent.click(screen.getByText('Close'));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('shows dialog title', () => {
    render(<ArtistInfoModal open={true} artist={mockArtist} onClose={vi.fn()} />);
    expect(screen.getByText('Artist Information')).toBeInTheDocument();
  });
});
