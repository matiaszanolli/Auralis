/**
 * TrackRow keyboard activation (#5658)
 *
 * The row's onKeyDown used to preventDefault() Enter/Space unconditionally,
 * so keydown bubbling from the nested Play/Pause and More buttons was
 * swallowed: the More menu could not be opened from the keyboard and the
 * current track could not be paused from its in-row button. These tests pin
 * the target-guarded behaviour — Enter/Space on a nested button reaches the
 * button, on the row itself it still plays.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import TrackRow from '../TrackRow';
import type { LibraryTrack } from '@/types/domain';

vi.mock('@/components/shared/Toast', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/components/shared/Toast')>()),
  useToast: () => ({ success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));

const track: LibraryTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
  albumArt: 'http://example.com/art.jpg',
} as LibraryTrack;

describe('TrackRow keyboard activation (#5658)', () => {
  it('plays the track when Enter is pressed on the row itself', async () => {
    const onPlay = vi.fn();
    render(<TrackRow track={track} index={0} onPlay={onPlay} />);

    const row = screen.getByRole('option', { name: 'Test Track by Test Artist' });
    row.focus();
    await userEvent.keyboard('{Enter}');

    expect(onPlay).toHaveBeenCalledWith(track.id);
  });

  it('plays the track when Space is pressed on the row itself', async () => {
    const onPlay = vi.fn();
    render(<TrackRow track={track} index={0} onPlay={onPlay} />);

    const row = screen.getByRole('option', { name: 'Test Track by Test Artist' });
    row.focus();
    await userEvent.keyboard(' ');

    expect(onPlay).toHaveBeenCalledWith(track.id);
  });

  it('opens the More menu from Enter on the More button without playing', async () => {
    const onPlay = vi.fn();
    render(<TrackRow track={track} index={0} onPlay={onPlay} />);

    const moreButton = screen.getByRole('button', { name: 'More options for Test Track' });
    moreButton.focus();
    await userEvent.keyboard('{Enter}');

    // The menu opens (anchored to the button rect, which jsdom reports as 0)
    expect(screen.getByRole('menu')).toBeInTheDocument();
    expect(onPlay).not.toHaveBeenCalled();
  });

  it('pauses from Enter on the Play/Pause button of the current playing track', async () => {
    const onPlay = vi.fn();
    const onPause = vi.fn();
    render(
      <TrackRow track={track} index={0} isCurrent isPlaying onPlay={onPlay} onPause={onPause} />
    );

    const pauseButton = screen.getByRole('button', { name: 'Pause Test Track' });
    pauseButton.focus();
    await userEvent.keyboard('{Enter}');

    expect(onPause).toHaveBeenCalledTimes(1);
    expect(onPlay).not.toHaveBeenCalled();
  });

  it('plays from Space on the Play button of a non-current track', async () => {
    const onPlay = vi.fn();
    render(<TrackRow track={track} index={0} onPlay={onPlay} />);

    const playButton = screen.getByRole('button', { name: 'Play Test Track' });
    playButton.focus();
    await userEvent.keyboard(' ');

    expect(onPlay).toHaveBeenCalledWith(track.id);
  });
});
