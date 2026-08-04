import { describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@/test/test-utils';
import { SidebarContent } from '../SidebarContent';

vi.mock('../NavigationSection', () => ({
  default: () => <div>Navigation items</div>,
}));

vi.mock('@/components/playlist/PlaylistList', () => ({
  default: () => <div>Playlists</div>,
}));

describe('SidebarContent accessibility', () => {
  it('exposes the Library section label as a heading', () => {
    render(<SidebarContent selectedItem="songs" onItemClick={vi.fn()} />);

    expect(
      screen.getByRole('heading', { name: 'Library', level: 2 })
    ).toBeInTheDocument();
  });
});
