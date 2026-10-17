/**
 * The seek bar and the global shortcut table share arrow keys (#5656)
 *
 * ArrowRight on the focused seek bar seeks +1s — and, through the window-level
 * listener, also ran the global "next track" shortcut (ArrowUp/Down also
 * changed the volume). Here the real ProgressBar and the real shortcut service
 * are wired together, so a regression in either side's contract shows up.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen } from '@/test/test-utils';
import { keyboardShortcuts } from '@/services/keyboardShortcutsService';
import ProgressBar from '../ProgressBar';

describe('ProgressBar keyboard vs global shortcuts (#5656)', () => {
  const next = vi.fn();
  const volumeUp = vi.fn();
  const togglePlay = vi.fn();

  beforeEach(() => {
    next.mockReset();
    volumeUp.mockReset();
    togglePlay.mockReset();
    keyboardShortcuts.clear();
    keyboardShortcuts.enable();
    keyboardShortcuts.register({ key: 'ArrowRight', description: 'Next', category: 'Playback' }, next);
    keyboardShortcuts.register({ key: 'ArrowUp', description: 'Volume up', category: 'Playback' }, volumeUp);
    keyboardShortcuts.register({ key: ' ', description: 'Play/Pause', category: 'Playback' }, togglePlay);
    keyboardShortcuts.startListening();
  });

  afterEach(() => {
    keyboardShortcuts.stopListening();
    keyboardShortcuts.clear();
  });

  function renderFocusedBar() {
    const onSeek = vi.fn();
    render(<ProgressBar currentTime={90} duration={200} onSeek={onSeek} />);
    const slider = screen.getByRole('slider');
    slider.focus();
    return { onSeek, slider };
  }

  it('ArrowRight only seeks; it does not skip the track', async () => {
    const { onSeek } = renderFocusedBar();

    await userEvent.keyboard('{ArrowRight}');

    expect(onSeek).toHaveBeenCalledTimes(1);
    expect(onSeek).toHaveBeenCalledWith(91);
    expect(next).not.toHaveBeenCalled();
  });

  it('ArrowUp only seeks; it does not change the volume', async () => {
    const { onSeek } = renderFocusedBar();

    await userEvent.keyboard('{ArrowUp}');

    expect(onSeek).toHaveBeenCalledWith(91);
    expect(volumeUp).not.toHaveBeenCalled();
  });

  it('Space on the focused seek bar still toggles playback (a slider does not use Space)', async () => {
    renderFocusedBar();

    await userEvent.keyboard(' ');

    expect(togglePlay).toHaveBeenCalledTimes(1);
  });
});
