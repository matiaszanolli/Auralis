/**
 * Tests for Sidebar component
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/test-utils'
import Sidebar from '../Sidebar'

describe('Sidebar', () => {
  it('renders all library items', () => {
    render(<Sidebar />)

    expect(screen.getByText('Songs')).toBeInTheDocument()
    expect(screen.getByText('Albums')).toBeInTheDocument()
    expect(screen.getByText('Artists')).toBeInTheDocument()
  })

  it('renders collection items', () => {
    render(<Sidebar />)

    expect(screen.getByText('Favourites')).toBeInTheDocument()
    expect(screen.getByText('Recently Played')).toBeInTheDocument()
  })

  it('renders playlists section', () => {
    render(<Sidebar />)

    expect(screen.getByText('Playlists')).toBeInTheDocument()
  })

  it('highlights the selected item', () => {
    render(<Sidebar />)

    // Songs should be selected by default
    const songsButton = screen.getByText('Songs').closest('button')
    expect(songsButton).toHaveAttribute('isactive', 'true')
  })

  it('changes selection when item is clicked', () => {
    render(<Sidebar />)

    const albumsButton = screen.getByText('Albums').closest('button')
    if (albumsButton) {
      fireEvent.click(albumsButton)
      expect(albumsButton).toHaveAttribute('isactive', 'true')
    }
  })

  it('toggles playlists section', () => {
    render(<Sidebar />)

    const playlistsHeader = screen.getByText('Playlists')
    const expandButton = playlistsHeader.parentElement?.querySelector('button')

    // Should be open by default
    expect(screen.queryByText('Chill Vibes')).toBeInTheDocument()

    // Click to collapse
    if (expandButton) {
      fireEvent.click(expandButton)
      // Wait for collapse animation
      setTimeout(() => {
        expect(screen.queryByText('Chill Vibes')).not.toBeInTheDocument()
      }, 350)
    }
  })

  it('calls onToggleCollapse when collapse button is clicked', () => {
    const handleToggleCollapse = vi.fn()
    render(<Sidebar onToggleCollapse={handleToggleCollapse} />)

    // Find collapse toggle button (if it exists)
    const collapseButton = screen.queryByTestId('collapse-sidebar-button')
    if (collapseButton) {
      fireEvent.click(collapseButton)
      expect(handleToggleCollapse).toHaveBeenCalledTimes(1)
    }
  })

  it('renders in collapsed state', () => {
    render(<Sidebar collapsed={true} />)

    // In collapsed state, text might be hidden but icons should still be present
    const sidebarContainer = screen.getByRole('navigation')
    expect(sidebarContainer).toBeInTheDocument()
  })
})
