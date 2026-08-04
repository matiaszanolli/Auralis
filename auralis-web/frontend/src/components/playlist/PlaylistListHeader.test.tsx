import { describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@/test/test-utils';
import { PlaylistListHeader } from './PlaylistListHeader';

describe('PlaylistListHeader keyboard interaction', () => {
  it('is focusable and toggles with Enter and Space', async () => {
    const user = userEvent.setup();
    const onExpandToggle = vi.fn();

    render(
      <PlaylistListHeader
        playlistCount={3}
        expanded={false}
        onExpandToggle={onExpandToggle}
        onCreateClick={vi.fn()}
      />
    );

    const header = screen.getByRole('button', { name: 'Expand playlists' });
    expect(header).toHaveAttribute('aria-expanded', 'false');

    await user.tab();
    expect(header).toHaveFocus();

    await user.keyboard('{Enter}');
    await user.keyboard(' ');

    expect(onExpandToggle).toHaveBeenCalledTimes(2);
  });

  it('prevents page scrolling when Space activates the header', () => {
    const onExpandToggle = vi.fn();

    render(
      <PlaylistListHeader
        playlistCount={0}
        expanded={true}
        onExpandToggle={onExpandToggle}
        onCreateClick={vi.fn()}
      />
    );

    const header = screen.getByRole('button', { name: 'Collapse playlists' });
    const event = new KeyboardEvent('keydown', {
      key: ' ',
      bubbles: true,
      cancelable: true,
    });

    header.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);
    expect(onExpandToggle).toHaveBeenCalledOnce();
    expect(header).toHaveAttribute('aria-expanded', 'true');
  });

  it('keeps the nested create button independent from the header toggle', async () => {
    const user = userEvent.setup();
    const onExpandToggle = vi.fn();
    const onCreateClick = vi.fn();

    render(
      <PlaylistListHeader
        playlistCount={1}
        expanded={false}
        onExpandToggle={onExpandToggle}
        onCreateClick={onCreateClick}
      />
    );

    const createButton = screen.getByRole('button', { name: 'Create playlist' });
    createButton.focus();
    await user.keyboard('{Enter}');

    expect(onCreateClick).toHaveBeenCalledOnce();
    expect(onExpandToggle).not.toHaveBeenCalled();
  });
});
