/**
 * App shell landmark regions (#4183)
 *
 * The app shell had no ARIA landmarks, so screen-reader users got one flat
 * region with no landmark navigation. These tests pin the three landmarks:
 * banner (top bar), navigation (sidebar), and main (content area).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

// PlaylistList pulls WS/API hooks; stub it so SidebarContent renders in
// isolation (we only care about the nav landmark wrapper).
vi.mock('@/components/playlist/PlaylistList', () => ({ default: () => null }));

import { AppMainContent } from '../AppMainContent';
import { AppTopBar } from '../AppTopBar';
import { SidebarContent } from '../../layouts/Sidebar/SidebarContent';

describe('App shell landmarks (#4183)', () => {
  it('AppMainContent exposes a single main landmark', () => {
    render(
      <AppMainContent>
        <div>content</div>
      </AppMainContent>
    );
    expect(screen.getAllByRole('main')).toHaveLength(1);
  });

  it('SidebarContent exposes a labelled navigation landmark', () => {
    render(<SidebarContent selectedItem="songs" onItemClick={vi.fn()} />);
    expect(
      screen.getByRole('navigation', { name: 'Library navigation' })
    ).toBeInTheDocument();
  });

  it('AppTopBar exposes a banner landmark', () => {
    render(
      <AppTopBar
        onSearch={vi.fn()}
        onOpenMobileDrawer={vi.fn()}
        title="Library"
        connectionStatus="connected"
        isMobile={false}
      />
    );
    expect(screen.getByRole('banner')).toBeInTheDocument();
  });
});
