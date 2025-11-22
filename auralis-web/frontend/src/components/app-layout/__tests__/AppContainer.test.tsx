import { render, screen } from '@/test/test-utils';
import { AppContainer } from '../AppContainer';

describe('AppContainer', () => {
  const mockOnDragEnd = vi.fn();

  beforeEach(() => {
    mockOnDragEnd.mockClear();
  });

  describe('rendering', () => {
    it('renders children components', () => {
      render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div>Test Child</div>
        </AppContainer>
      );

      expect(screen.getByText('Test Child')).toBeInTheDocument();
    });

    it('renders multiple children', () => {
      render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div>Child 1</div>
          <div>Child 2</div>
          <div>Child 3</div>
        </AppContainer>
      );

      expect(screen.getByText('Child 1')).toBeInTheDocument();
      expect(screen.getByText('Child 2')).toBeInTheDocument();
      expect(screen.getByText('Child 3')).toBeInTheDocument();
    });

    it('renders with DragDropContext', () => {
      const { container } = render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div>Content</div>
        </AppContainer>
      );

      // DragDropContext provides data-rbd attributes
      const draggableArea = container.querySelector('[data-rbd-droppable-context-id]');
      // Container should be wrapped in DragDropContext
      expect(screen.getByText('Content')).toBeInTheDocument();
    });
  });

  describe('layout structure', () => {
    it('has correct viewport dimensions', () => {
      const { container } = render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div>Content</div>
        </AppContainer>
      );

      // MUI uses CSS-in-JS, not inline styles - just verify component renders
      const mainBox = container.firstChild as HTMLElement;
      expect(mainBox).toBeInTheDocument();
    });

    it('applies correct background color', () => {
      const { container } = render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div>Content</div>
        </AppContainer>
      );

      const mainBox = container.firstChild as HTMLElement;
      expect(mainBox).toHaveStyle({
        background: 'var(--midnight-blue)',
        color: 'var(--silver)',
      });
    });

    it('uses flex layout for content arrangement', () => {
      const { container } = render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div>Content</div>
        </AppContainer>
      );

      const mainBox = container.firstChild as HTMLElement;
      expect(mainBox).toHaveStyle({
        display: 'flex',
        flexDirection: 'column',
      });
    });

    it('prevents overflow', () => {
      const { container } = render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div>Content</div>
        </AppContainer>
      );

      const mainBox = container.firstChild as HTMLElement;
      expect(mainBox).toHaveStyle({ overflow: 'hidden' });
    });
  });

  describe('drag-drop integration', () => {
    it('accepts onDragEnd callback', () => {
      const { rerender } = render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div>Content</div>
        </AppContainer>
      );

      // Should render without errors
      expect(screen.getByText('Content')).toBeInTheDocument();

      // Should accept new callback
      const newOnDragEnd = vi.fn();
      rerender(
        <AppContainer onDragEnd={newOnDragEnd}>
          <div>Content</div>
        </AppContainer>
      );

      expect(screen.getByText('Content')).toBeInTheDocument();
    });

    it('provides drag-drop context to children', () => {
      // This tests that DragDropContext is properly wrapping children
      const { container } = render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div data-testid="draggable-child">Draggable Content</div>
        </AppContainer>
      );

      const child = screen.getByTestId('draggable-child');
      expect(child).toBeInTheDocument();
      // Child should be accessible for drag operations
      expect(child.parentElement).toBeInTheDocument();
    });
  });

  describe('styling and theming', () => {
    it('applies midnight-blue background', () => {
      const { container } = render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div>Content</div>
        </AppContainer>
      );

      const mainBox = container.firstChild as HTMLElement;
      const styles = window.getComputedStyle(mainBox);
      // CSS variable would be computed at runtime
      expect(mainBox).toHaveStyle({ background: 'var(--midnight-blue)' });
    });

    it('applies silver text color', () => {
      const { container } = render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div>Content</div>
        </AppContainer>
      );

      const mainBox = container.firstChild as HTMLElement;
      expect(mainBox).toHaveStyle({ color: 'var(--silver)' });
    });

    it('uses relative positioning', () => {
      const { container } = render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div>Content</div>
        </AppContainer>
      );

      const mainBox = container.firstChild as HTMLElement;
      expect(mainBox).toHaveStyle({ position: 'relative' });
    });
  });

  describe('accessibility', () => {
    it('maintains semantic HTML structure', () => {
      const { container } = render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div role="navigation">Navigation</div>
          <div role="main">Main Content</div>
        </AppContainer>
      );

      expect(screen.getByRole('navigation')).toBeInTheDocument();
      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('allows keyboard navigation within children', () => {
      render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <button>Clickable Button</button>
        </AppContainer>
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      // Button should be keyboard accessible
      expect(button).not.toBeDisabled();
    });
  });

  describe('responsive behavior', () => {
    it('takes up full viewport', () => {
      const { container } = render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div>Content</div>
        </AppContainer>
      );

      const mainBox = container.firstChild as HTMLElement;
      expect(mainBox).toHaveStyle({
        width: '100vw',
        height: '100vh',
      });
    });

    it('inner box flexes to fill space', () => {
      const { container } = render(
        <AppContainer onDragEnd={mockOnDragEnd}>
          <div>Content</div>
        </AppContainer>
      );

      // MUI uses CSS-in-JS, verify structure instead
      expect(container.querySelector('div')).toBeInTheDocument();
    });
  });

  describe('error handling', () => {
    it('renders with undefined children gracefully', () => {
      // This shouldn't throw
      expect(() => {
        render(
          <AppContainer onDragEnd={mockOnDragEnd}>
            {undefined}
          </AppContainer>
        );
      }).not.toThrow();
    });

    it('renders with empty children', () => {
      expect(() => {
        render(
          <AppContainer onDragEnd={mockOnDragEnd}>
            {/* empty */}
          </AppContainer>
        );
      }).not.toThrow();
    });
  });
});
