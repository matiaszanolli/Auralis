/**
 * KeyboardShortcutsHeader — close button accessibility (#4448)
 *
 * The close IconButton previously rendered only <Close /> with no aria-label,
 * so screen readers announced a bare "button". It now carries an explicit
 * accessible name.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { KeyboardShortcutsHeader } from '../KeyboardShortcutsHeader';

describe('KeyboardShortcutsHeader close button (#4448)', () => {
  it('exposes an accessible name on the close button', () => {
    render(<KeyboardShortcutsHeader onClose={vi.fn()} />);

    expect(
      screen.getByRole('button', { name: /close keyboard shortcuts/i })
    ).toBeInTheDocument();
  });

  it('invokes onClose when the close button is activated', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<KeyboardShortcutsHeader onClose={onClose} />);

    await user.click(
      screen.getByRole('button', { name: /close keyboard shortcuts/i })
    );

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
