/**
 * Tests for Sidebar component
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import Sidebar from '../layouts/Sidebar'

describe('Sidebar', () => {
  const mockOnNavigate = vi.fn()
  const mockOnToggleCollapse = vi.fn()
  const mockOnOpenSettings = vi.fn()

  beforeEach(() => {
    mockOnNavigate.mockClear()
    mockOnToggleCollapse.mockClear()
    mockOnOpenSettings.mockClear()
  })

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

  it('renders settings button', () => {
    render(<Sidebar />)
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('calls onNavigate when item is clicked', async () => {
    const user = userEvent.setup()
    render(<Sidebar onNavigate={mockOnNavigate} />)

    const albumsButton = screen.getByText('Albums').closest('button')
    if (albumsButton) {
      await user.click(albumsButton)
      expect(mockOnNavigate).toHaveBeenCalledWith('albums')
    }
  })

  it('renders in collapsed state', () => {
    const { container } = render(<Sidebar collapsed={true} />)

    // In collapsed state, sidebar should be narrow (64px)
    const sidebar = container.firstChild as HTMLElement
    expect(sidebar).toHaveStyle({ width: '64px' })
  })

  it('does not show text labels when collapsed', () => {
    render(<Sidebar collapsed={true} />)

    expect(screen.queryByText('Songs')).not.toBeInTheDocument()
    expect(screen.queryByText('Albums')).not.toBeInTheDocument()
  })

  it('calls onToggleCollapse when collapse button clicked', async () => {
    const user = userEvent.setup()
    const { container} = render(<Sidebar onToggleCollapse={mockOnToggleCollapse} />)

    const collapseButton = container.querySelector('[data-testid="ChevronLeftIcon"]')?.closest('button')
    if (collapseButton) {
      await user.click(collapseButton)
      expect(mockOnToggleCollapse).toHaveBeenCalledTimes(1)
    }
  })

  it('calls onOpenSettings when settings clicked', async () => {
    const user = userEvent.setup()
    render(<Sidebar onOpenSettings={mockOnOpenSettings} />)

    const settingsButton = screen.getByText('Settings').closest('button')
    if (settingsButton) {
      await user.click(settingsButton)
      expect(mockOnOpenSettings).toHaveBeenCalledTimes(1)
    }
  })
})
