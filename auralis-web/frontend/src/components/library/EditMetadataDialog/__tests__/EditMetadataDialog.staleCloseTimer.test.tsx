/**
 * EditMetadataDialog stale auto-close timer (#5634)
 *
 * #5397 made this dialog stay mounted (hidden via `open`). The save
 * success path arms a 1s setTimeout(onClose) that nothing cancelled, so
 * manually closing and opening another track's editor within that second
 * got the NEW dialog closed by the OLD save's timer. The timer is now
 * cancelled on every open-state change (and unmount).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { EditMetadataDialog } from '../EditMetadataDialog';

const onClose = vi.fn();

function dialogJsx(open: boolean, trackId: number) {
  return (
    <EditMetadataDialog
      open={open}
      trackId={trackId}
      currentMetadata={{ title: 'Song' }}
      onClose={onClose}
    />
  );
}

async function saveViaUi() {
  fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Song II' } });
  fireEvent.click(screen.getByRole('button', { name: /save/i }));
  // Flush the PUT and the state updates that arm the 1s timer.
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe('EditMetadataDialog auto-close timer (#5634)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response(JSON.stringify({}), { status: 200 })))
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("a save's pending auto-close cannot close an editor reopened within the window", async () => {
    const { rerender } = render(dialogJsx(true, 1));

    await saveViaUi();

    // Manual close, then a new editing session inside the timer's window.
    rerender(dialogJsx(false, 1));
    rerender(dialogJsx(true, 2));
    await act(async () => {
      vi.advanceTimersByTime(1000);
    });

    expect(onClose).not.toHaveBeenCalled();
  });

  it('the auto-close still fires when the dialog stays open', async () => {
    render(dialogJsx(true, 1));

    await saveViaUi();
    expect(onClose).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(1000);
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
