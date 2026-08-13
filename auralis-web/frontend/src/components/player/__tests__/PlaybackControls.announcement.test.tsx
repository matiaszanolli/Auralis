/**
 * Play/pause is announced to screen readers (#4474)
 *
 * The play/pause button swaps its `aria-label`, but Space toggles playback from
 * anywhere via useKeyboardShortcuts — the button need never hold focus, so
 * nothing reads the new label out. Track *changes* got a live region in #2362;
 * play/pause state had none.
 *
 * The region must stay empty on mount: rendering the current state immediately
 * would make every page load announce "Paused" unprompted.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import PlaybackControls from '../PlaybackControls';

const noop = () => {};

function renderControls(isPlaying: boolean) {
  return render(
    <PlaybackControls
      isPlaying={isPlaying}
      onPlay={noop}
      onPause={noop}
      onNext={noop}
      onPrevious={noop}
    />
  );
}

const announcement = () => screen.getByTestId('playback-controls-announcement');

describe('PlaybackControls play/pause announcement (#4474)', () => {
  it('exposes a polite, atomic live region', () => {
    renderControls(false);

    const region = announcement();
    expect(region).toHaveAttribute('role', 'status');
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toHaveAttribute('aria-atomic', 'true');
  });

  it('is empty on mount so a page load does not announce a state nobody changed', () => {
    renderControls(false);
    expect(announcement()).toHaveTextContent('');

    // Same when mounting mid-playback.
    renderControls(true);
    expect(screen.getAllByTestId('playback-controls-announcement')[1]).toHaveTextContent('');
  });

  it('announces "Playing" when playback starts', () => {
    const { rerender } = renderControls(false);

    rerender(
      <PlaybackControls
        isPlaying
        onPlay={noop}
        onPause={noop}
        onNext={noop}
        onPrevious={noop}
      />
    );

    expect(announcement()).toHaveTextContent('Playing');
  });

  it('announces "Paused" when playback stops', () => {
    const { rerender } = renderControls(true);

    rerender(
      <PlaybackControls
        isPlaying={false}
        onPlay={noop}
        onPause={noop}
        onNext={noop}
        onPrevious={noop}
      />
    );

    expect(announcement()).toHaveTextContent('Paused');
  });

  it('tracks repeated toggles, so a keyboard user hears each one', () => {
    const { rerender } = renderControls(false);
    const withPlaying = (isPlaying: boolean) => (
      <PlaybackControls
        isPlaying={isPlaying}
        onPlay={noop}
        onPause={noop}
        onNext={noop}
        onPrevious={noop}
      />
    );

    rerender(withPlaying(true));
    expect(announcement()).toHaveTextContent('Playing');

    rerender(withPlaying(false));
    expect(announcement()).toHaveTextContent('Paused');

    rerender(withPlaying(true));
    expect(announcement()).toHaveTextContent('Playing');
  });

  it('does not announce when an unrelated prop changes', () => {
    const { rerender } = renderControls(true);

    rerender(
      <PlaybackControls
        isPlaying
        onPlay={noop}
        onPause={noop}
        onNext={noop}
        onPrevious={noop}
        isLoading
      />
    );

    expect(announcement()).toHaveTextContent('');
    expect(screen.getByTestId('playback-controls-loading')).toBeInTheDocument();
  });

  it('keeps the region visually hidden', () => {
    renderControls(false);
    // Visually hidden rather than display:none — display:none is not announced.
    expect(announcement()).toHaveStyle({ position: 'absolute', overflow: 'hidden' });
  });

  it('still swaps the button aria-label (the existing affordance is unchanged)', () => {
    const { rerender } = renderControls(false);
    expect(screen.getByLabelText('Play')).toBeInTheDocument();

    rerender(
      <PlaybackControls
        isPlaying
        onPlay={vi.fn()}
        onPause={vi.fn()}
        onNext={vi.fn()}
        onPrevious={vi.fn()}
      />
    );

    expect(screen.getByLabelText('Pause')).toBeInTheDocument();
  });
});
