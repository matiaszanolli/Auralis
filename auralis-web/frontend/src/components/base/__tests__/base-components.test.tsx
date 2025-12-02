import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@/test/test-utils';
import {
  Container,
  Stack,
  Grid,
  Checkbox,
  Toggle,
  Alert,
  ProgressBar,
  ErrorBoundary,
} from '../index';

describe('Base Components', () => {
  describe('Layout Components', () => {
    describe('Container', () => {
      it('renders children correctly', () => {
        render(<Container>Test content</Container>);
        expect(screen.getByText('Test content')).toBeInTheDocument();
      });

      it('applies maxWidth prop', () => {
        const { container } = render(
          <Container maxWidth="lg">Test</Container>
        );
        const element = container.firstChild as HTMLElement;
        expect(element.style.maxWidth).toBe('1024px');
      });

      it('supports custom className', () => {
        const { container } = render(
          <Container className="custom-class">Test</Container>
        );
        expect(container.firstChild).toHaveClass('custom-class');
      });
    });

    describe('Stack', () => {
      it('renders children in correct direction', () => {
        const { container } = render(
          <Stack direction="row">
            <div>Item 1</div>
            <div>Item 2</div>
          </Stack>
        );
        const stack = container.firstChild as HTMLElement;
        expect(stack.style.flexDirection).toBe('row');
      });

      it('applies spacing correctly', () => {
        const { container } = render(
          <Stack spacing="lg">Test</Stack>
        );
        const stack = container.firstChild as HTMLElement;
        expect(stack.style.gap).toBe('24px');
      });
    });

    describe('Grid', () => {
      it('renders grid layout', () => {
        const { container } = render(
          <Grid columns={3}>
            <div>Item 1</div>
            <div>Item 2</div>
            <div>Item 3</div>
          </Grid>
        );
        const grid = container.firstChild as HTMLElement;
        expect(grid.style.display).toBe('grid');
      });
    });
  });

  describe('Input Components', () => {
    describe('Checkbox', () => {
      it('renders checkbox with label', () => {
        render(<Checkbox label="Accept" />);
        expect(screen.getByText('Accept')).toBeInTheDocument();
      });

      it('displays error state', () => {
        render(<Checkbox error="Must accept" />);
        expect(screen.getByText('Must accept')).toBeInTheDocument();
      });

      it('handles checked state', () => {
        const { container } = render(<Checkbox defaultChecked />);
        const input = container.querySelector('input') as HTMLInputElement;
        expect(input.checked).toBe(true);
      });
    });

    describe('Toggle', () => {
      it('renders toggle switch', () => {
        const { container } = render(<Toggle />);
        const input = container.querySelector('input');
        expect(input?.type).toBe('checkbox');
      });

      it('renders with label', () => {
        render(<Toggle label="Enable feature" />);
        expect(screen.getByText('Enable feature')).toBeInTheDocument();
      });
    });
  });

  describe('Display Components', () => {
    describe('Alert', () => {
      it('renders alert message', () => {
        render(<Alert>Alert message</Alert>);
        expect(screen.getByText('Alert message')).toBeInTheDocument();
      });

      it('calls onClose when close button clicked', () => {
        const onClose = vi.fn();
        render(<Alert onClose={onClose}>Alert</Alert>);
        const closeButton = screen.getByLabelText('Close alert');
        closeButton.click();
        expect(onClose).toHaveBeenCalled();
      });

      it('supports different variants', () => {
        const variants = ['info', 'success', 'warning', 'error'] as const;
        variants.forEach((variant) => {
          const { unmount } = render(<Alert variant={variant}>Alert</Alert>);
          expect(screen.getByText('Alert')).toBeInTheDocument();
          unmount();
        });
      });
    });

    describe('ProgressBar', () => {
      it('renders progress bar with correct percentage', () => {
        const { container } = render(<ProgressBar value={75} />);
        const bar = container.querySelector('div[style*="width"]') as HTMLElement;
        expect(bar?.style.width).toContain('75');
      });

      it('displays label and value', () => {
        render(<ProgressBar value={50} label="Download" showValue />);
        expect(screen.getByText('Download')).toBeInTheDocument();
        expect(screen.getByText('50%')).toBeInTheDocument();
      });

      it('clamps value to max', () => {
        const { container } = render(<ProgressBar value={150} max={100} />);
        const bar = container.querySelector('div[style*="width"]') as HTMLElement;
        expect(bar?.style.width).toBe('100%');
      });
    });
  });

  describe('Feedback Components', () => {
    describe('ErrorBoundary', () => {
      const ThrowError = () => {
        throw new Error('Test error');
      };

      it('catches errors and displays error UI', () => {
        const onError = vi.fn();
        render(
          <ErrorBoundary onError={onError}>
            <ThrowError />
          </ErrorBoundary>
        );
        expect(screen.getByText('Something went wrong')).toBeInTheDocument();
      });

      it('calls onError callback', () => {
        const onError = vi.fn();
        render(
          <ErrorBoundary onError={onError}>
            <ThrowError />
          </ErrorBoundary>
        );
        expect(onError).toHaveBeenCalled();
      });

      it('renders children when no error', () => {
        render(
          <ErrorBoundary>
            <div>Normal content</div>
          </ErrorBoundary>
        );
        expect(screen.getByText('Normal content')).toBeInTheDocument();
      });

      it('recovers from error with retry', () => {
        let shouldThrow = true;
        const ThrowConditional = () => {
          if (shouldThrow) throw new Error('Test error');
          return <div>Recovered</div>;
        };

        const { rerender } = render(
          <ErrorBoundary>
            <ThrowConditional />
          </ErrorBoundary>
        );
        expect(screen.getByText('Something went wrong')).toBeInTheDocument();

        const retryButton = screen.getByText('Try again');
        shouldThrow = false;
        retryButton.click();
        rerender(
          <ErrorBoundary>
            <ThrowConditional />
          </ErrorBoundary>
        );
      });
    });
  });
});
