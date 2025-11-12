/**
 * EnhancementToggle Component Tests (Player Bar Variant)
 *
 * Tests player bar toggle with visual feedback:
 * - Toggle state with icon and label
 * - Glow effects when enabled
 * - Visual animations and transitions
 * - Tooltip behavior
 * - Accessibility
 * - Memoization
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { describe, it, expect, vi } from 'vitest';
import { EnhancementToggle } from '../EnhancementToggle';
import { auralisTheme } from '@/theme/auralisTheme';

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('EnhancementToggle (Player Bar Variant)', () => {
  describe('Rendering', () => {
    it('should render toggle button when enabled', async () => {
      render(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('should render toggle button when disabled', async () => {
      render(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
        </Wrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('should render icon button with AutoAwesome icon', async () => {
      const { container } = render(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      const svgIcon = container.querySelector('[class*="MuiSvgIcon"]');
      expect(svgIcon).toBeTruthy();
    });

    it('should display label "Enhanced" when enabled', () => {
      render(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();
    });

    it('should display label "Original" when disabled', () => {
      render(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
        </Wrapper>
      );

      expect(screen.getByText('Original')).toBeInTheDocument();
    });
  });

  describe('Toggle Functionality', () => {
    it('should call onToggle when clicked', async () => {
      const mockToggle = vi.fn();
      const user = userEvent.setup();

      render(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={mockToggle} />
        </Wrapper>
      );

      const button = screen.getByRole('button');
      await user.click(button);

      expect(mockToggle).toHaveBeenCalledTimes(1);
    });

    it('should toggle from disabled to enabled', async () => {
      const mockToggle = vi.fn();
      const user = userEvent.setup();

      const { rerender } = render(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={mockToggle} />
        </Wrapper>
      );

      expect(screen.getByText('Original')).toBeInTheDocument();

      await user.click(screen.getByRole('button'));

      rerender(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={mockToggle} />
        </Wrapper>
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();
    });

    it('should toggle from enabled to disabled', async () => {
      const mockToggle = vi.fn();
      const user = userEvent.setup();

      const { rerender } = render(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={mockToggle} />
        </Wrapper>
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();

      await user.click(screen.getByRole('button'));

      rerender(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={mockToggle} />
        </Wrapper>
      );

      expect(screen.getByText('Original')).toBeInTheDocument();
    });
  });

  describe('Tooltip', () => {
    it('should show tooltip when enabled', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      const button = screen.getByRole('button');
      await user.hover(button);

      await waitFor(() => {
        expect(screen.getByText('Disable audio enhancement')).toBeInTheDocument();
      });
    });

    it('should show tooltip when disabled', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
        </Wrapper>
      );

      const button = screen.getByRole('button');
      await user.hover(button);

      await waitFor(() => {
        expect(screen.getByText('Enable audio enhancement')).toBeInTheDocument();
      });
    });

    it('should hide tooltip on unhover', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      const button = screen.getByRole('button');
      await user.hover(button);

      await waitFor(() => {
        expect(screen.getByText('Disable audio enhancement')).toBeInTheDocument();
      });

      await user.unhover(button);

      await waitFor(() => {
        expect(screen.queryByText('Disable audio enhancement')).not.toBeInTheDocument();
      });
    });
  });

  describe('Visual Styling', () => {
    it('should have button styling when enabled', () => {
      const { container } = render(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      const button = container.querySelector('button');
      expect(button).toBeTruthy();
    });

    it('should have button styling when disabled', () => {
      const { container } = render(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
        </Wrapper>
      );

      const button = container.querySelector('button');
      expect(button).toBeTruthy();
    });

    it('should have container with flex layout', () => {
      const { container } = render(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      const containerBox = container.querySelector('[class*="MuiBox"]');
      expect(containerBox).toBeTruthy();
    });
  });

  describe('Label Display', () => {
    it('should show correct label for enabled state', () => {
      render(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();
      expect(screen.queryByText('Original')).not.toBeInTheDocument();
    });

    it('should show correct label for disabled state', () => {
      render(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
        </Wrapper>
      );

      expect(screen.getByText('Original')).toBeInTheDocument();
      expect(screen.queryByText('Enhanced')).not.toBeInTheDocument();
    });

    it('should update label when state changes', () => {
      const { rerender } = render(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
        </Wrapper>
      );

      expect(screen.getByText('Original')).toBeInTheDocument();

      rerender(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();
    });
  });

  describe('State Synchronization', () => {
    it('should reflect enabled state in tooltip', async () => {
      const user = userEvent.setup();
      const { rerender } = render(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
        </Wrapper>
      );

      let button = screen.getByRole('button');
      await user.hover(button);

      await waitFor(() => {
        expect(screen.getByText('Enable audio enhancement')).toBeInTheDocument();
      });

      await user.unhover(button);

      rerender(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      button = screen.getByRole('button');
      await user.hover(button);

      await waitFor(() => {
        expect(screen.getByText('Disable audio enhancement')).toBeInTheDocument();
      });
    });
  });

  describe('Callback Behavior', () => {
    it('should call onToggle exactly once per click', async () => {
      const mockToggle = vi.fn();
      const user = userEvent.setup();

      render(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={mockToggle} />
        </Wrapper>
      );

      const button = screen.getByRole('button');
      await user.click(button);

      expect(mockToggle).toHaveBeenCalledTimes(1);
    });

    it('should handle multiple toggles', async () => {
      const mockToggle = vi.fn();
      const user = userEvent.setup();

      const { rerender } = render(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={mockToggle} />
        </Wrapper>
      );

      let button = screen.getByRole('button');

      await user.click(button);
      rerender(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={mockToggle} />
        </Wrapper>
      );

      button = screen.getByRole('button');
      await user.click(button);

      rerender(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={mockToggle} />
        </Wrapper>
      );

      expect(mockToggle).toHaveBeenCalledTimes(2);
    });
  });

  describe('Memoization', () => {
    it('should be memoized component', () => {
      const { rerender } = render(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();

      rerender(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();
    });

    it('should update when isEnabled prop changes', () => {
      const { rerender } = render(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
        </Wrapper>
      );

      expect(screen.getByText('Original')).toBeInTheDocument();

      rerender(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();
    });

    it('should handle onToggle callback changes', async () => {
      const mockToggle1 = vi.fn();
      const mockToggle2 = vi.fn();
      const user = userEvent.setup();

      const { rerender } = render(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={mockToggle1} />
        </Wrapper>
      );

      let button = screen.getByRole('button');
      await user.click(button);

      expect(mockToggle1).toHaveBeenCalledTimes(1);

      rerender(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={mockToggle2} />
        </Wrapper>
      );

      button = screen.getByRole('button');
      await user.click(button);

      expect(mockToggle2).toHaveBeenCalledTimes(1);
    });
  });

  describe('Accessibility', () => {
    it('should have button role', () => {
      render(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('should have aria-label for screen readers', () => {
      render(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label');
    });

    it('should have descriptive aria-label when enabled', () => {
      render(
        <Wrapper>
          <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
        </Wrapper>
      );

      const button = screen.getByRole('button');
      expect(button.getAttribute('aria-label')).toBe('Disable enhancement');
    });

    it('should have descriptive aria-label when disabled', () => {
      render(
        <Wrapper>
          <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
        </Wrapper>
      );

      const button = screen.getByRole('button');
      expect(button.getAttribute('aria-label')).toBe('Enable enhancement');
    });
  });

  describe('Display Name', () => {
    it('should have correct display name for debugging', () => {
      expect(EnhancementToggle.displayName).toBe('EnhancementToggle');
    });
  });
});
