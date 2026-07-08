/**
 * ArtistTrackRow Tests (issue #3931)
 *
 * Verifies keyboard accessibility: the row is focusable, exposes an
 * aria-label describing the play action, and Enter/Space trigger the same
 * onTrackClick callback as a mouse click — previously only onClick was
 * wired up, making the row unreachable by keyboard-only users.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { ArtistTrackRow } from '../ArtistTrackRow';
import type { DetailTrack } from '@/types/domain';

const track: DetailTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 200,
  filepath: '/music/test.flac',
} as DetailTrack;

const formatDuration = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;

function renderRow(onTrackClick: (t: DetailTrack) => void) {
  return render(
    <table>
      <tbody>
        <ArtistTrackRow
          track={track}
          index={0}
          isCurrentTrack={false}
          isPlaying={false}
          onTrackClick={onTrackClick}
          formatDuration={formatDuration}
        />
      </tbody>
    </table>
  );
}

describe('ArtistTrackRow', () => {
  it('is focusable and has an aria-label describing the play action', () => {
    renderRow(vi.fn());
    const row = screen.getByRole('row', { name: 'Play Test Track' });
    expect(row).toHaveAttribute('tabIndex', '0');
  });

  it('calls onTrackClick on mouse click', async () => {
    const onTrackClick = vi.fn();
    renderRow(onTrackClick);

    await userEvent.click(screen.getByRole('row', { name: 'Play Test Track' }));

    expect(onTrackClick).toHaveBeenCalledWith(track);
  });

  it('calls onTrackClick when Enter is pressed', async () => {
    const onTrackClick = vi.fn();
    renderRow(onTrackClick);

    const row = screen.getByRole('row', { name: 'Play Test Track' });
    row.focus();
    await userEvent.keyboard('{Enter}');

    expect(onTrackClick).toHaveBeenCalledWith(track);
  });

  it('calls onTrackClick when Space is pressed', async () => {
    const onTrackClick = vi.fn();
    renderRow(onTrackClick);

    const row = screen.getByRole('row', { name: 'Play Test Track' });
    row.focus();
    await userEvent.keyboard(' ');

    expect(onTrackClick).toHaveBeenCalledWith(track);
  });
});
