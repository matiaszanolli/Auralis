import { render, screen } from '@/test/test-utils';
import { describe, expect, it, vi } from 'vitest';
import type { LibraryTrack } from '@/types/domain';
import { TrackListViewContent } from '../TrackListViewContent';

vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: () => ({
    getVirtualItems: () => [{ index: 0, size: 56, start: 0 }],
    getTotalSize: () => 56,
    options: { scrollMargin: 0 },
  }),
}));

vi.mock('@/components/library/Items/tracks/SelectableTrackRow', () => ({
  default: ({ track }: { track: LibraryTrack }) => (
    <div role="option" aria-label={`${track.title} by ${track.artist}`} />
  ),
}));

const track = {
  id: 1,
  title: 'Semantic Song',
  artist: 'Accessible Artist',
  album: 'ARIA Album',
  duration: 180,
  filepath: '/music/semantic.flac',
} as LibraryTrack;

describe('TrackListViewContent accessibility', () => {
  it('owns every track option with a labelled listbox (#4906)', () => {
    render(
      <TrackListViewContent
        tracks={[track]}
        hasMore={false}
        isLoadingMore={false}
        totalTracks={1}
        isPlaying={false}
        selectedTracks={new Set()}
        isSelected={() => false}
        onToggleSelect={vi.fn()}
        onTrackPlay={vi.fn()}
        onPause={vi.fn()}
        onEditMetadata={vi.fn()}
      />
    );

    const listbox = screen.getByRole('listbox', { name: 'Track list' });
    const option = screen.getByRole('option', { name: 'Semantic Song by Accessible Artist' });
    expect(listbox).toContainElement(option);
    expect(listbox).toHaveAttribute('aria-multiselectable', 'true');
  });
});
