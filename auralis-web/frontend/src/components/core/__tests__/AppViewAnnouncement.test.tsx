import { render, screen } from '@/test/test-utils';
import { describe, expect, it } from 'vitest';
import { AppViewAnnouncement } from '../AppViewAnnouncement';

describe('AppViewAnnouncement', () => {
  it('politely announces each active library view (#4961)', () => {
    const { rerender } = render(<AppViewAnnouncement view="songs" />);
    const status = screen.getByRole('status');

    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(status).toHaveAttribute('aria-atomic', 'true');
    expect(status).toHaveTextContent('Songs view');

    rerender(<AppViewAnnouncement view="albums" />);
    expect(status).toHaveTextContent('Albums view');

    rerender(<AppViewAnnouncement view="playlist-42" />);
    expect(status).toHaveTextContent('Playlist view');
  });
});
