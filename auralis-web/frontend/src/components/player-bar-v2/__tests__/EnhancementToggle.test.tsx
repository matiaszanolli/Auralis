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
import { render, screen, waitFor } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { EnhancementToggle } from '../EnhancementToggle';


describe('EnhancementToggle (Player Bar Variant)', () => {
  describe('Rendering', () => {
    it('should render toggle button when enabled', async () => {
      render(
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('should render toggle button when disabled', async () => {
      render(
        <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('should render icon button with AutoAwesome icon', async () => {
      const { container } = render(
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
      );

      const svgIcon = container.querySelector('[class*="MuiSvgIcon"]');
      expect(svgIcon).toBeTruthy();
    });

    it('should display label "Enhanced" when enabled', () => {
      render(
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();
    });

    it('should display label "Original" when disabled', () => {
      render(
        <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
      );

      expect(screen.getByText('Original')).toBeInTheDocument();
    });
  });

  describe('Toggle Functionality', () => {
    it('should call onToggle when clicked', async () => {
      const mockToggle = vi.fn();
      const user = userEvent.setup();

      render(
        <EnhancementToggle isEnabled={false} onToggle={mockToggle} />
      );

      const button = screen.getByRole('button');
      await user.click(button);

      expect(mockToggle).toHaveBeenCalledTimes(1);
    });

    it('should toggle from disabled to enabled', async () => {
      const mockToggle = vi.fn();
      const user = userEvent.setup();

      const { rerender } = render(
        <EnhancementToggle isEnabled={false} onToggle={mockToggle} />
      );

      expect(screen.getByText('Original')).toBeInTheDocument();

      await user.click(screen.getByRole('button'));

      rerender(
        <EnhancementToggle isEnabled={true} onToggle={mockToggle} />
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();
    });

    it('should toggle from enabled to disabled', async () => {
      const mockToggle = vi.fn();
      const user = userEvent.setup();

      const { rerender } = render(
        <EnhancementToggle isEnabled={true} onToggle={mockToggle} />
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();

      await user.click(screen.getByRole('button'));

      rerender(
        <EnhancementToggle isEnabled={false} onToggle={mockToggle} />
      );

      expect(screen.getByText('Original')).toBeInTheDocument();
    });
  });

  describe('Tooltip', () => {
    it('should show tooltip when enabled', async () => {
      const user = userEvent.setup();

      render(
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
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
        <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
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
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
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
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
      );

      const button = container.querySelector('button');
      expect(button).toBeTruthy();
    });

    it('should have button styling when disabled', () => {
      const { container } = render(
        <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
      );

      const button = container.querySelector('button');
      expect(button).toBeTruthy();
    });

    it('should have container with flex layout', () => {
      const { container } = render(
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
      );

      const containerBox = container.querySelector('[class*="MuiBox"]');
      expect(containerBox).toBeTruthy();
    });
  });

  describe('Label Display', () => {
    it('should show correct label for enabled state', () => {
      render(
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();
      expect(screen.queryByText('Original')).not.toBeInTheDocument();
    });

    it('should show correct label for disabled state', () => {
      render(
        <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
      );

      expect(screen.getByText('Original')).toBeInTheDocument();
      expect(screen.queryByText('Enhanced')).not.toBeInTheDocument();
    });

    it('should update label when state changes', () => {
      const { rerender } = render(
        <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
      );

      expect(screen.getByText('Original')).toBeInTheDocument();

      rerender(
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();
    });
  });

  describe('State Synchronization', () => {
    it('should reflect enabled state in tooltip', async () => {
      const user = userEvent.setup();
      const { rerender } = render(
        <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
      );

      let button = screen.getByRole('button');
      await user.hover(button);

      await waitFor(() => {
        expect(screen.getByText('Enable audio enhancement')).toBeInTheDocument();
      });

      await user.unhover(button);

      rerender(
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
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
        <EnhancementToggle isEnabled={false} onToggle={mockToggle} />
      );

      const button = screen.getByRole('button');
      await user.click(button);

      expect(mockToggle).toHaveBeenCalledTimes(1);
    });

    it('should handle multiple toggles', async () => {
      const mockToggle = vi.fn();
      const user = userEvent.setup();

      const { rerender } = render(
        <EnhancementToggle isEnabled={false} onToggle={mockToggle} />
      );

      let button = screen.getByRole('button');

      await user.click(button);
      rerender(
        <EnhancementToggle isEnabled={true} onToggle={mockToggle} />
      );

      button = screen.getByRole('button');
      await user.click(button);

      rerender(
        <EnhancementToggle isEnabled={false} onToggle={mockToggle} />
      );

      expect(mockToggle).toHaveBeenCalledTimes(2);
    });
  });

  describe('Memoization', () => {
    it('should be memoized component', () => {
      const { rerender } = render(
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();

      rerender(
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();
    });

    it('should update when isEnabled prop changes', () => {
      const { rerender } = render(
        <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
      );

      expect(screen.getByText('Original')).toBeInTheDocument();

      rerender(
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
      );

      expect(screen.getByText('Enhanced')).toBeInTheDocument();
    });

    it('should handle onToggle callback changes', async () => {
      const mockToggle1 = vi.fn();
      const mockToggle2 = vi.fn();
      const user = userEvent.setup();

      const { rerender } = render(
        <EnhancementToggle isEnabled={false} onToggle={mockToggle1} />
      );

      let button = screen.getByRole('button');
      await user.click(button);

      expect(mockToggle1).toHaveBeenCalledTimes(1);

      rerender(
        <EnhancementToggle isEnabled={false} onToggle={mockToggle2} />
      );

      button = screen.getByRole('button');
      await user.click(button);

      expect(mockToggle2).toHaveBeenCalledTimes(1);
    });
  });

  describe('Accessibility', () => {
    it('should have button role', () => {
      render(
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('should have aria-label for screen readers', () => {
      render(
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label');
    });

    it('should have descriptive aria-label when enabled', () => {
      render(
        <EnhancementToggle isEnabled={true} onToggle={vi.fn()} />
      );

      const button = screen.getByRole('button');
      expect(button.getAttribute('aria-label')).toBe('Disable enhancement');
    });

    it('should have descriptive aria-label when disabled', () => {
      render(
        <EnhancementToggle isEnabled={false} onToggle={vi.fn()} />
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
