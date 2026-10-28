/**
 * The sidebar highlight follows the app's current view (#6014)
 *
 * The highlight came from a local `selectedItem` that started at 'songs', so the 1/2/3 shortcuts
 * (which change the view without going through the sidebar) left it stale, and a remount (desktop <->
 * mobile drawer) reset it to Songs whatever view was showing.
 */

import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@/test/test-utils';
import Sidebar from '../Sidebar';

const current = () => screen.getAllByRole('button').filter((b) => b.getAttribute('aria-current') === 'page');

describe('Sidebar activeView (#6014)', () => {
  it('highlights the item for the current view, not the default', () => {
    render(<Sidebar activeView="albums" />);

    expect(current().map((b) => b.textContent)).toEqual([expect.stringMatching(/albums/i)]);
  });

  it('follows a view change made elsewhere (a shortcut) without a click', () => {
    const { rerender } = render(<Sidebar activeView="songs" />);
    expect(current()[0]).toHaveTextContent(/songs/i);

    rerender(<Sidebar activeView="artists" />);

    expect(current()).toHaveLength(1);
    expect(current()[0]).toHaveTextContent(/artists/i);
  });

  it('a freshly mounted sidebar shows the current view, not Songs', () => {
    const { unmount } = render(<Sidebar activeView="artists" />);
    unmount();

    render(<Sidebar activeView="artists" />);

    expect(current()[0]).toHaveTextContent(/artists/i);
  });

  it('still reports clicks through onNavigate', async () => {
    const onNavigate = vi.fn();
    render(<Sidebar activeView="songs" onNavigate={onNavigate} />);

    await userEvent.setup().click(screen.getByRole('button', { name: /albums/i }));

    expect(onNavigate).toHaveBeenCalledWith('albums');
  });

  it('without activeView it keeps its old local-selection behaviour', async () => {
    render(<Sidebar />);
    expect(current()[0]).toHaveTextContent(/songs/i);

    await userEvent.setup().click(screen.getByRole('button', { name: /albums/i }));

    expect(current()[0]).toHaveTextContent(/albums/i);
  });
});
