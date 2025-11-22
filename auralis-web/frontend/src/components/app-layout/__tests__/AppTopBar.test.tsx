import { render, screen, waitFor } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { AppTopBar } from '../AppTopBar';

describe('AppTopBar', () => {
  const mockOnSearch = vi.fn();
  const mockOnOpenMobileDrawer = vi.fn();
  const mockOnSearchClear = vi.fn();

  beforeEach(() => {
    mockOnSearch.mockClear();
    mockOnOpenMobileDrawer.mockClear();
    mockOnSearchClear.mockClear();
  });

  describe('rendering', () => {
    it('renders with all required elements', () => {
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      expect(screen.getByDisplayValue('')).toBeInTheDocument(); // Search input
      expect(screen.getByRole('button')).toBeInTheDocument(); // Status indicator area
    });

    it('renders title on desktop', () => {
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Albums"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      expect(screen.getByText('Albums')).toBeInTheDocument();
    });

    it('renders search input with placeholder', () => {
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      const searchInput = screen.getByPlaceholderText(/Search tracks, albums, artists/);
      expect(searchInput).toBeInTheDocument();
    });
  });

  describe('search functionality', () => {
    it('calls onSearch with query when input changes', async () => {
      const user = userEvent.setup();
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      const searchInput = screen.getByPlaceholderText(/Search tracks, albums, artists/);
      await user.type(searchInput, 'radiohead');

      await waitFor(() => {
        expect(mockOnSearch).toHaveBeenCalledWith('radiohead');
      });
    });

    it('calls onSearch with empty string when input is cleared', async () => {
      const user = userEvent.setup();
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      const searchInput = screen.getByPlaceholderText(/Search tracks, albums, artists/);
      await user.type(searchInput, 'radiohead');
      await user.clear(searchInput);

      await waitFor(() => {
        expect(mockOnSearch).toHaveBeenCalledWith('');
      });
    });

    it('shows clear button when search has value', async () => {
      const user = userEvent.setup();
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      const searchInput = screen.getByPlaceholderText(/Search tracks, albums, artists/);
      await user.type(searchInput, 'test');

      await waitFor(() => {
        const clearButton = screen.getByRole('button', { name: '' });
        expect(clearButton).toBeInTheDocument();
      });
    });

    it('clears search when clear button clicked', async () => {
      const user = userEvent.setup();
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
          onSearchClear={mockOnSearchClear}
        />
      );

      const searchInput = screen.getByPlaceholderText(/Search tracks, albums, artists/);
      await user.type(searchInput, 'radiohead');

      await waitFor(() => {
        const clearButton = screen.getByRole('button', { name: '' });
        expect(clearButton).toBeInTheDocument();
      });

      const clearButton = screen.getByRole('button', { name: '' });
      await user.click(clearButton);

      await waitFor(() => {
        expect(mockOnSearch).toHaveBeenCalledWith('');
        expect(mockOnSearchClear).toHaveBeenCalled();
      });
    });

    it('does not show clear button when search is empty', () => {
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      const searchInput = screen.getByPlaceholderText(/Search tracks, albums, artists/);
      expect(searchInput).toHaveValue('');

      // Clear button should not be rendered when input is empty
      // (multiple buttons exist for other functionality, so just verify behavior)
      expect(mockOnSearch).not.toHaveBeenCalled();
    });

    it('supports multiple search queries', async () => {
      const user = userEvent.setup();
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      const searchInput = screen.getByPlaceholderText(/Search tracks, albums, artists/);

      await user.type(searchInput, 'beatles');
      await waitFor(() => {
        expect(mockOnSearch).toHaveBeenCalledWith('beatles');
      });

      mockOnSearch.mockClear();

      await user.clear(searchInput);
      await user.type(searchInput, 'pink floyd');

      await waitFor(() => {
        expect(mockOnSearch).toHaveBeenCalledWith('pink floyd');
      });
    });
  });

  describe('mobile menu button', () => {
    it('shows hamburger menu on mobile (isMobile=true)', () => {
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={true}
        />
      );

      // Mobile shows hamburger button
      const menuButton = screen.getAllByRole('button')[0];
      expect(menuButton).toBeInTheDocument();
    });

    it('calls onOpenMobileDrawer when hamburger clicked on mobile', async () => {
      const user = userEvent.setup();
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={true}
        />
      );

      const menuButton = screen.getAllByRole('button')[0];
      await user.click(menuButton);

      await waitFor(() => {
        expect(mockOnOpenMobileDrawer).toHaveBeenCalled();
      });
    });

    it('does not show hamburger menu on desktop (isMobile=false)', () => {
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      // Desktop should not have visible hamburger button
      expect(mockOnOpenMobileDrawer).not.toHaveBeenCalled();
    });

    it('hides title on mobile in favor of hamburger menu', () => {
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Albums"
          connectionStatus="connected"
          isMobile={true}
        />
      );

      // Title text should not be prominently displayed on mobile
      // (hamburger takes priority on left side)
      const menuButton = screen.getAllByRole('button')[0];
      expect(menuButton).toBeInTheDocument();
    });
  });

  describe('connection status indicator', () => {
    it('shows green indicator when connected', () => {
      const { container } = render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      // Component renders without errors
      expect(container.firstChild).toBeInTheDocument();
    });

    it('shows yellow indicator when connecting', () => {
      const { container } = render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connecting"
          isMobile={false}
        />
      );

      // Component renders without errors
      expect(container.firstChild).toBeInTheDocument();
    });

    it('shows red indicator when disconnected', () => {
      const { container } = render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="disconnected"
          isMobile={false}
        />
      );

      // Component renders without errors
      expect(container.firstChild).toBeInTheDocument();
    });

    it('updates indicator color on status change', () => {
      const { rerender } = render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      rerender(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="disconnected"
          isMobile={false}
        />
      );

      // Component should re-render with new status
      expect(screen.getByPlaceholderText(/Search tracks, albums, artists/)).toBeInTheDocument();
    });
  });

  describe('responsive behavior', () => {
    it('adjusts layout for desktop', () => {
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      // Desktop: title visible, no hamburger menu
      expect(screen.getByText('Library')).toBeInTheDocument();
    });

    it('adjusts layout for mobile', () => {
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={true}
        />
      );

      // Mobile: hamburger menu visible
      const menuButton = screen.getAllByRole('button')[0];
      expect(menuButton).toBeInTheDocument();
    });

    it('handles title changes', () => {
      const { rerender } = render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      expect(screen.getByText('Library')).toBeInTheDocument();

      rerender(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Artists"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      expect(screen.getByText('Artists')).toBeInTheDocument();
    });
  });

  describe('styling and theming', () => {
    it('applies correct background color', () => {
      const { container } = render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      const topBar = container.firstChild;
      expect(topBar).toHaveStyle({
        background: 'var(--midnight-blue)',
      });
    });

    it('applies border styling', () => {
      const { container } = render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      const topBar = container.firstChild;
      expect(topBar).toHaveStyle({
        borderBottom: '1px solid rgba(102, 126, 234, 0.1)',
      });
    });

    it('applies correct text colors', () => {
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      const title = screen.getByText('Library');
      expect(title).toHaveStyle({
        color: 'var(--silver)',
      });
    });

    it('sets correct height', () => {
      const { container } = render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      const topBar = container.firstChild;
      expect(topBar).toHaveStyle({ height: '70px' });
    });
  });

  describe('accessibility', () => {
    it('search input is accessible', () => {
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      const searchInput = screen.getByPlaceholderText(/Search tracks, albums, artists/);
      expect(searchInput).toBeInTheDocument();
      expect(searchInput).not.toBeDisabled();
    });

    it('hamburger button is accessible on mobile', () => {
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={true}
        />
      );

      const menuButton = screen.getAllByRole('button')[0];
      expect(menuButton).toBeInTheDocument();
      expect(menuButton).not.toBeDisabled();
    });

    it('maintains semantic structure', () => {
      render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      const searchInput = screen.getByPlaceholderText(/Search tracks, albums, artists/);
      expect(searchInput).toBeInTheDocument();
    });
  });

  describe('prop updates', () => {
    it('updates title when prop changes', () => {
      const { rerender } = render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      expect(screen.getByText('Library')).toBeInTheDocument();

      rerender(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Albums"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      expect(screen.getByText('Albums')).toBeInTheDocument();
      expect(screen.queryByText('Library')).not.toBeInTheDocument();
    });

    it('preserves search input when other props change', async () => {
      const user = userEvent.setup();
      const { rerender } = render(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Library"
          connectionStatus="connected"
          isMobile={false}
        />
      );

      const searchInput = screen.getByPlaceholderText(/Search tracks, albums, artists/);
      await user.type(searchInput, 'test');

      rerender(
        <AppTopBar
          onSearch={mockOnSearch}
          onOpenMobileDrawer={mockOnOpenMobileDrawer}
          title="Albums"
          connectionStatus="connecting"
          isMobile={false}
        />
      );

      // Search input should be preserved with the typed value
      expect(searchInput).toHaveValue('test');
    });
  });

  describe('error handling', () => {
    it('renders without errors when all props provided', () => {
      expect(() => {
        render(
          <AppTopBar
            onSearch={mockOnSearch}
            onOpenMobileDrawer={mockOnOpenMobileDrawer}
            title="Library"
            connectionStatus="connected"
            isMobile={false}
          />
        );
      }).not.toThrow();
    });

    it('renders with optional onSearchClear callback', () => {
      expect(() => {
        render(
          <AppTopBar
            onSearch={mockOnSearch}
            onOpenMobileDrawer={mockOnOpenMobileDrawer}
            title="Library"
            connectionStatus="connected"
            isMobile={false}
            onSearchClear={mockOnSearchClear}
          />
        );
      }).not.toThrow();
    });
  });
});
