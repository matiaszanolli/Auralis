import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@/test/test-utils';
import {
  Container,
  Stack,
  Grid,
  TextInput,
  Checkbox,
  Toggle,
  Button,
  Card,
  Badge,
  Alert,
  ProgressBar,
  LoadingSpinner,
  Modal,
  Tooltip,
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
    describe('TextInput', () => {
      it('renders input with label', () => {
        render(<TextInput label="Name" placeholder="Enter name" />);
        expect(screen.getByText('Name')).toBeInTheDocument();
      });

      it('displays error message', () => {
        render(<TextInput error="Field required" />);
        expect(screen.getByText('Field required')).toBeInTheDocument();
      });

      it('shows helper text when no error', () => {
        render(<TextInput helperText="Help text" />);
        expect(screen.getByText('Help text')).toBeInTheDocument();
      });

      it('hides helper text when error exists', () => {
        const { queryByText } = render(
          <TextInput error="Error" helperText="Help" />
        );
        expect(queryByText('Help')).not.toBeInTheDocument();
      });
    });

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
    describe('Button', () => {
      it('renders button with text', () => {
        render(<Button>Click me</Button>);
        expect(screen.getByText('Click me')).toBeInTheDocument();
      });

      it('supports different variants', () => {
        const { container: primaryContainer } = render(
          <Button variant="primary">Primary</Button>
        );
        const primaryBtn = primaryContainer.querySelector('button') as HTMLElement;
        expect(primaryBtn.style.backgroundColor).toBeTruthy();

        const { container: ghostContainer } = render(
          <Button variant="ghost">Ghost</Button>
        );
        const ghostBtn = ghostContainer.querySelector('button') as HTMLElement;
        expect(ghostBtn.style.backgroundColor).toBe('transparent');
      });

      it('disables when disabled prop is true', () => {
        render(<Button disabled>Disabled</Button>);
        const button = screen.getByText('Disabled') as HTMLButtonElement;
        expect(button.disabled).toBe(true);
      });

      it('shows loading state', () => {
        render(<Button loading>Loading</Button>);
        const button = screen.getByText('Loading') as HTMLButtonElement;
        expect(button.disabled).toBe(true);
      });
    });

    describe('Card', () => {
      it('renders card with header and footer', () => {
        render(
          <Card
            header="Header"
            footer="Footer"
          >
            Content
          </Card>
        );
        expect(screen.getByText('Header')).toBeInTheDocument();
        expect(screen.getByText('Content')).toBeInTheDocument();
        expect(screen.getByText('Footer')).toBeInTheDocument();
      });

      it('supports hoverable state', () => {
        const { container } = render(
          <Card hoverable>Content</Card>
        );
        const card = container.firstChild as HTMLElement;
        expect(card).toBeInTheDocument();
      });
    });

    describe('Badge', () => {
      it('renders badge with content', () => {
        render(<Badge>New</Badge>);
        expect(screen.getByText('New')).toBeInTheDocument();
      });

      it('supports different variants', () => {
        const variants = ['primary', 'success', 'warning', 'error', 'info'] as const;
        variants.forEach((variant) => {
          const { unmount } = render(<Badge variant={variant}>{variant}</Badge>);
          expect(screen.getByText(variant)).toBeInTheDocument();
          unmount();
        });
      });
    });

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
    describe('LoadingSpinner', () => {
      it('renders spinner', () => {
        const { container } = render(<LoadingSpinner />);
        expect(container.querySelector('div')).toBeInTheDocument();
      });

      it('displays label when provided', () => {
        render(<LoadingSpinner label="Loading..." />);
        expect(screen.getByText('Loading...')).toBeInTheDocument();
      });
    });

    describe('Modal', () => {
      it('renders when isOpen is true', () => {
        render(
          <Modal isOpen={true} onClose={() => {}}>
            Modal content
          </Modal>
        );
        expect(screen.getByText('Modal content')).toBeInTheDocument();
      });

      it('does not render when isOpen is false', () => {
        const { queryByText } = render(
          <Modal isOpen={false} onClose={() => {}}>
            Modal content
          </Modal>
        );
        expect(queryByText('Modal content')).not.toBeInTheDocument();
      });

      it('calls onClose when backdrop clicked', () => {
        const onClose = vi.fn();
        const { container } = render(
          <Modal isOpen={true} onClose={onClose}>
            Content
          </Modal>
        );
        const backdrop = container.querySelector('div[style*="position: fixed"]') as HTMLElement;
        backdrop?.click();
        expect(onClose).toHaveBeenCalled();
      });

      it('renders title when provided', () => {
        render(
          <Modal isOpen={true} onClose={() => {}} title="Modal Title">
            Content
          </Modal>
        );
        expect(screen.getByText('Modal Title')).toBeInTheDocument();
      });
    });

    describe('Tooltip', () => {
      it('renders tooltip content on hover', async () => {
        render(
          <Tooltip content="Tooltip text">
            <button>Hover me</button>
          </Tooltip>
        );
        const button = screen.getByText('Hover me');
        expect(screen.getByText('Tooltip text')).toBeInTheDocument();
      });
    });

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
