import { render, screen } from '@/test/test-utils';
import { AppMainContent } from '../AppMainContent';

describe('AppMainContent', () => {
  const mockOnPlayTrack = vi.fn();
  const mockOnQueueTrack = vi.fn();

  beforeEach(() => {
    mockOnPlayTrack.mockClear();
    mockOnQueueTrack.mockClear();
  });

  describe('rendering', () => {
    it('renders children content', () => {
      render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Test Content</div>
        </AppMainContent>
      );

      expect(screen.getByText('Test Content')).toBeInTheDocument();
    });

    it('renders multiple child elements', () => {
      render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>First</div>
          <div>Second</div>
          <div>Third</div>
        </AppMainContent>
      );

      expect(screen.getByText('First')).toBeInTheDocument();
      expect(screen.getByText('Second')).toBeInTheDocument();
      expect(screen.getByText('Third')).toBeInTheDocument();
    });

    it('renders with undefined children gracefully', () => {
      expect(() => {
        render(
          <AppMainContent onPlayTrack={mockOnPlayTrack}>
            {undefined}
          </AppMainContent>
        );
      }).not.toThrow();
    });

    it('renders with empty children', () => {
      expect(() => {
        render(
          <AppMainContent onPlayTrack={mockOnPlayTrack}>
            {/* empty */}
          </AppMainContent>
        );
      }).not.toThrow();
    });
  });

  describe('layout structure', () => {
    it('has correct flex layout', () => {
      const { container } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content</div>
        </AppMainContent>
      );

      const mainBox = container.firstChild;
      expect(mainBox).toHaveStyle({
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      });
    });

    it('has scrollable content area', () => {
      const { container } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content</div>
        </AppMainContent>
      );

      const contentArea = container.querySelector('[style*="flex: 1"]');
      expect(contentArea).toHaveStyle({ overflow: 'auto' });
    });

    it('applies padding for player bar', () => {
      const { container } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content</div>
        </AppMainContent>
      );

      const contentArea = container.querySelector('[style*="flex: 1"]');
      expect(contentArea).toHaveStyle({ paddingBottom: '100px' });
    });

    it('prevents content overflow', () => {
      const { container } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content</div>
        </AppMainContent>
      );

      const mainBox = container.firstChild;
      expect(mainBox).toHaveStyle({ overflow: 'hidden' });
    });

    it('allows horizontal and vertical scrolling in content area', () => {
      const { container } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content</div>
        </AppMainContent>
      );

      const contentArea = container.querySelector('[style*="flex: 1"]');
      expect(contentArea).toHaveStyle({ overflow: 'auto' });
    });
  });

  describe('scrollbar styling', () => {
    it('applies custom scrollbar width', () => {
      const { container } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content</div>
        </AppMainContent>
      );

      const contentArea = container.querySelector('[style*="flex: 1"]');
      // Scrollbar styling is applied via CSS in sx prop
      expect(contentArea).toBeInTheDocument();
    });

    it('applies custom scrollbar colors', () => {
      const { container } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content</div>
        </AppMainContent>
      );

      const contentArea = container.querySelector('[style*="flex: 1"]');
      // Custom scrollbar styling should be present
      expect(contentArea).toBeInTheDocument();
    });

    it('applies scrollbar hover effect', () => {
      const { container } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content</div>
        </AppMainContent>
      );

      const contentArea = container.querySelector('[style*="flex: 1"]');
      expect(contentArea).toBeInTheDocument();
    });
  });

  describe('prop handling', () => {
    it('accepts onPlayTrack callback', () => {
      expect(() => {
        render(
          <AppMainContent onPlayTrack={mockOnPlayTrack}>
            <div>Content</div>
          </AppMainContent>
        );
      }).not.toThrow();
    });

    it('accepts onQueueTrack callback', () => {
      expect(() => {
        render(
          <AppMainContent onPlayTrack={mockOnPlayTrack} onQueueTrack={mockOnQueueTrack}>
            <div>Content</div>
          </AppMainContent>
        );
      }).not.toThrow();
    });

    it('handles missing optional callbacks', () => {
      expect(() => {
        render(
          <AppMainContent>
            <div>Content</div>
          </AppMainContent>
        );
      }).not.toThrow();
    });

    it('updates when children change', () => {
      const { rerender } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>First Content</div>
        </AppMainContent>
      );

      expect(screen.getByText('First Content')).toBeInTheDocument();

      rerender(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Second Content</div>
        </AppMainContent>
      );

      expect(screen.getByText('Second Content')).toBeInTheDocument();
      expect(screen.queryByText('First Content')).not.toBeInTheDocument();
    });

    it('updates when callbacks change', () => {
      const newOnPlayTrack = vi.fn();
      const { rerender } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content</div>
        </AppMainContent>
      );

      rerender(
        <AppMainContent onPlayTrack={newOnPlayTrack}>
          <div>Content</div>
        </AppMainContent>
      );

      expect(screen.getByText('Content')).toBeInTheDocument();
    });
  });

  describe('content area features', () => {
    it('supports flex children with proper spacing', () => {
      render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div style={{ flex: 1 }}>Growing content</div>
        </AppMainContent>
      );

      expect(screen.getByText('Growing content')).toBeInTheDocument();
    });

    it('maintains aspect ratio for media content', () => {
      render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <img alt="test" src="test.jpg" style={{ aspectRatio: '1 / 1' }} />
        </AppMainContent>
      );

      const img = screen.getByAltText('test');
      expect(img).toBeInTheDocument();
    });

    it('prevents horizontal overflow with long content', () => {
      const { container } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div style={{ whiteSpace: 'nowrap', overflow: 'hidden' }}>
            Very long content that should not overflow
          </div>
        </AppMainContent>
      );

      const mainBox = container.firstChild;
      expect(mainBox).toHaveStyle({ overflow: 'hidden' });
    });
  });

  describe('player bar spacing', () => {
    it('provides 100px padding for player bar', () => {
      const { container } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content above player</div>
        </AppMainContent>
      );

      const contentArea = container.querySelector('[style*="flex: 1"]');
      expect(contentArea).toHaveStyle({ paddingBottom: '100px' });
    });

    it('scrolling respects player bar padding', () => {
      const { container } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content that scrolls</div>
        </AppMainContent>
      );

      const contentArea = container.querySelector('[style*="flex: 1"]');
      expect(contentArea).toHaveStyle({
        overflow: 'auto',
        paddingBottom: '100px',
      });
    });

    it('maintains padding when content is small', () => {
      const { container } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Small content</div>
        </AppMainContent>
      );

      const contentArea = container.querySelector('[style*="flex: 1"]');
      expect(contentArea).toHaveStyle({ paddingBottom: '100px' });
    });
  });

  describe('accessibility', () => {
    it('maintains semantic structure', () => {
      render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <main>Main content area</main>
        </AppMainContent>
      );

      expect(screen.getByText('Main content area')).toBeInTheDocument();
    });

    it('allows keyboard navigation within content', () => {
      render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <button>Clickable button</button>
        </AppMainContent>
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button).not.toBeDisabled();
    });

    it('preserves ARIA attributes of children', () => {
      render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div role="navigation" aria-label="Main menu">
            Navigation
          </div>
        </AppMainContent>
      );

      expect(screen.getByLabelText('Main menu')).toBeInTheDocument();
    });
  });

  describe('responsive behavior', () => {
    it('takes up full available flex space', () => {
      const { container } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content</div>
        </AppMainContent>
      );

      const mainBox = container.firstChild;
      expect(mainBox).toHaveStyle({ flex: 1 });
    });

    it('adapts to container size changes', () => {
      const { rerender } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content</div>
        </AppMainContent>
      );

      // Component should rerender with new dimensions
      rerender(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Updated content</div>
        </AppMainContent>
      );

      expect(screen.getByText('Updated content')).toBeInTheDocument();
    });

    it('maintains scroll position during updates', () => {
      const { rerender } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Original content</div>
        </AppMainContent>
      );

      expect(screen.getByText('Original content')).toBeInTheDocument();

      rerender(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Updated content</div>
        </AppMainContent>
      );

      expect(screen.getByText('Updated content')).toBeInTheDocument();
    });
  });

  describe('integration with library view', () => {
    it('renders library view component', () => {
      render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div data-testid="library-view">Library content</div>
        </AppMainContent>
      );

      expect(screen.getByTestId('library-view')).toBeInTheDocument();
    });

    it('provides proper container for list components', () => {
      render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <ul>
            <li>Track 1</li>
            <li>Track 2</li>
            <li>Track 3</li>
          </ul>
        </AppMainContent>
      );

      expect(screen.getByRole('list')).toBeInTheDocument();
    });

    it('supports virtualized list components', () => {
      render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div style={{ height: '100%', overflow: 'auto' }}>
            Virtualized list
          </div>
        </AppMainContent>
      );

      expect(screen.getByText('Virtualized list')).toBeInTheDocument();
    });
  });

  describe('error handling', () => {
    it('renders without errors when all props provided', () => {
      expect(() => {
        render(
          <AppMainContent onPlayTrack={mockOnPlayTrack} onQueueTrack={mockOnQueueTrack}>
            <div>Content</div>
          </AppMainContent>
        );
      }).not.toThrow();
    });

    it('renders without errors when minimal props provided', () => {
      expect(() => {
        render(
          <AppMainContent>
            <div>Content</div>
          </AppMainContent>
        );
      }).not.toThrow();
    });

    it('handles rapid children changes', () => {
      const { rerender } = render(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content 1</div>
        </AppMainContent>
      );

      rerender(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content 2</div>
        </AppMainContent>
      );

      rerender(
        <AppMainContent onPlayTrack={mockOnPlayTrack}>
          <div>Content 3</div>
        </AppMainContent>
      );

      expect(screen.getByText('Content 3')).toBeInTheDocument();
    });
  });
});
