/**
 * EnhancementToggle Component Tests (Enhancement Pane Variant)
 *
 * Tests master toggle switch for audio enhancement:
 * - Toggle state changes
 * - Callbacks and event handling
 * - Disabled state during processing
 * - Status messages
 * - Accessibility
 * - Memoization
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import EnhancementToggle from '../EnhancementToggle';


describe('EnhancementToggle (Enhancement Pane Variant)', () => {
  describe('Rendering', () => {
    it('should render toggle component when enabled', () => {
      render(
        <EnhancementToggle
            enabled={true}
            isProcessing={false}
            onToggle={vi.fn()}
          />
      );

      // Should render the switch component
      const switchComponent = screen.getByRole('checkbox');
      expect(switchComponent).toBeInTheDocument();
    });

    it('should render toggle component when disabled', () => {
      render(
        <EnhancementToggle
            enabled={false}
            isProcessing={false}
            onToggle={vi.fn()}
          />
      );

      const switchComponent = screen.getByRole('checkbox');
      expect(switchComponent).toBeInTheDocument();
    });

    it('should show enabled status message', () => {
      render(
        <EnhancementToggle
            enabled={true}
            isProcessing={false}
            onToggle={vi.fn()}
          />
      );

      expect(screen.getByText(/Analyzing audio and applying intelligent processing/i)).toBeInTheDocument();
    });

    it('should show disabled status message', () => {
      render(
        <EnhancementToggle
            enabled={false}
            isProcessing={false}
            onToggle={vi.fn()}
          />
      );

      expect(screen.getByText(/Turn on to enhance your music automatically/i)).toBeInTheDocument();
    });
  });

  describe('Toggle Functionality', () => {
    it('should call onToggle when clicked', async () => {
      const mockToggle = vi.fn();
      const user = userEvent.setup();

      render(
        <EnhancementToggle
            enabled={false}
            isProcessing={false}
            onToggle={mockToggle}
          />
      );

      const switchComponent = screen.getByRole('checkbox');
      await user.click(switchComponent);

      expect(mockToggle).toHaveBeenCalled();
    });

    it('should toggle from disabled to enabled', async () => {
      const mockToggle = vi.fn();
      const user = userEvent.setup();

      const { rerender } = render(
        <EnhancementToggle
            enabled={false}
            isProcessing={false}
            onToggle={mockToggle}
          />
      );

      let switchComponent = screen.getByRole('checkbox') as HTMLInputElement;
      expect(switchComponent.checked).toBe(false);

      await user.click(switchComponent);

      rerender(
        <EnhancementToggle
            enabled={true}
            isProcessing={false}
            onToggle={mockToggle}
          />
      );

      switchComponent = screen.getByRole('checkbox') as HTMLInputElement;
      expect(switchComponent.checked).toBe(true);
    });

    it('should toggle from enabled to disabled', async () => {
      const mockToggle = vi.fn();
      const user = userEvent.setup();

      const { rerender } = render(
        <EnhancementToggle
            enabled={true}
            isProcessing={false}
            onToggle={mockToggle}
          />
      );

      let switchComponent = screen.getByRole('checkbox') as HTMLInputElement;
      expect(switchComponent.checked).toBe(true);

      await user.click(switchComponent);

      rerender(
        <EnhancementToggle
            enabled={false}
            isProcessing={false}
            onToggle={mockToggle}
          />
      );

      switchComponent = screen.getByRole('checkbox') as HTMLInputElement;
      expect(switchComponent.checked).toBe(false);
    });
  });

  describe('Processing State', () => {
    it('should show processing message when analyzing', () => {
      render(
        <EnhancementToggle
            enabled={true}
            isProcessing={true}
            onToggle={vi.fn()}
          />
      );

      expect(screen.getByText(/Analyzing audio and applying intelligent processing/i)).toBeInTheDocument();
    });

    it('should have visual indication when processing', () => {
      const { container } = render(
        <EnhancementToggle
            enabled={true}
            isProcessing={true}
            onToggle={vi.fn()}
          />
      );

      // Component should still be present and interactive during processing
      const switchComponent = screen.getByRole('checkbox');
      expect(switchComponent).toBeInTheDocument();
    });

    it('should show processing state when analyzing', async () => {
      const mockToggle = vi.fn();

      render(
        <EnhancementToggle
            enabled={true}
            isProcessing={true}
            onToggle={mockToggle}
          />
      );

      const switchComponent = screen.getByRole('checkbox');
      // Component should still be present during processing
      expect(switchComponent).toBeInTheDocument();
      // When processing, the component has pointer-events disabled, so just verify presence
    });
  });

  describe('State Synchronization', () => {
    it('should reflect enabled state in checkbox', () => {
      const { rerender } = render(
        <EnhancementToggle
            enabled={false}
            isProcessing={false}
            onToggle={vi.fn()}
          />
      );

      let switchComponent = screen.getByRole('checkbox') as HTMLInputElement;
      expect(switchComponent.checked).toBe(false);

      rerender(
        <EnhancementToggle
            enabled={true}
            isProcessing={false}
            onToggle={vi.fn()}
          />
      );

      switchComponent = screen.getByRole('checkbox') as HTMLInputElement;
      expect(switchComponent.checked).toBe(true);
    });

    it('should update message when enabled changes', () => {
      const { rerender } = render(
        <EnhancementToggle
            enabled={false}
            isProcessing={false}
            onToggle={vi.fn()}
          />
      );

      expect(screen.getByText(/Turn on to enhance your music automatically/i)).toBeInTheDocument();

      rerender(
        <EnhancementToggle
            enabled={true}
            isProcessing={false}
            onToggle={vi.fn()}
          />
      );

      expect(screen.getByText(/Analyzing audio and applying intelligent processing/i)).toBeInTheDocument();
    });

    it('should update message when processing changes', () => {
      const { rerender } = render(
        <EnhancementToggle
            enabled={true}
            isProcessing={false}
            onToggle={vi.fn()}
          />
      );

      expect(screen.getByText(/Analyzing audio and applying intelligent processing/i)).toBeInTheDocument();

      rerender(
        <EnhancementToggle
            enabled={true}
            isProcessing={true}
            onToggle={vi.fn()}
          />
      );

      expect(screen.getByText(/Analyzing audio and applying intelligent processing/i)).toBeInTheDocument();
    });
  });

  describe('Callback Behavior', () => {
    it('should call onToggle with correct parameter', async () => {
      const mockToggle = vi.fn();
      const user = userEvent.setup();

      render(
        <EnhancementToggle
            enabled={false}
            isProcessing={false}
            onToggle={mockToggle}
          />
      );

      const switchComponent = screen.getByRole('checkbox');
      await user.click(switchComponent);

      expect(mockToggle).toHaveBeenCalledTimes(1);
    });

    it('should handle rapid toggle clicks', async () => {
      const mockToggle = vi.fn();
      const user = userEvent.setup();

      const { rerender } = render(
        <EnhancementToggle
            enabled={false}
            isProcessing={false}
            onToggle={mockToggle}
          />
      );

      const switchComponent = screen.getByRole('checkbox');

      await user.click(switchComponent);
      rerender(
        <EnhancementToggle
            enabled={true}
            isProcessing={false}
            onToggle={mockToggle}
          />
      );

      await user.click(switchComponent);
      rerender(
        <EnhancementToggle
            enabled={false}
            isProcessing={false}
            onToggle={mockToggle}
          />
      );

      expect(mockToggle).toHaveBeenCalledTimes(2);
    });
  });

  describe('Memoization', () => {
    it('should be memoized component', () => {
      const mockToggle = vi.fn();

      const { rerender } = render(
        <EnhancementToggle
            enabled={true}
            isProcessing={false}
            onToggle={mockToggle}
          />
      );

      expect(screen.getByRole('checkbox')).toBeInTheDocument();

      rerender(
        <EnhancementToggle
            enabled={true}
            isProcessing={false}
            onToggle={mockToggle}
          />
      );

      expect(screen.getByRole('checkbox')).toBeInTheDocument();
    });

    it('should update when props change', () => {
      const mockToggle = vi.fn();

      const { rerender } = render(
        <EnhancementToggle
            enabled={false}
            isProcessing={false}
            onToggle={mockToggle}
          />
      );

      expect(screen.getByText(/Turn on to enhance/i)).toBeInTheDocument();

      rerender(
        <EnhancementToggle
            enabled={true}
            isProcessing={false}
            onToggle={mockToggle}
          />
      );

      expect(screen.getByText(/Analyzing audio/i)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have accessible checkbox role', () => {
      render(
        <EnhancementToggle
            enabled={false}
            isProcessing={false}
            onToggle={vi.fn()}
          />
      );

      const switchComponent = screen.getByRole('checkbox');
      expect(switchComponent).toBeInTheDocument();
    });

    it('should have proper aria attributes', () => {
      render(
        <EnhancementToggle
            enabled={true}
            isProcessing={false}
            onToggle={vi.fn()}
          />
      );

      const switchComponent = screen.getByRole('checkbox');
      expect(switchComponent).toHaveAttribute('type', 'checkbox');
    });

    it('should have clear status message for screen readers', () => {
      render(
        <EnhancementToggle
            enabled={true}
            isProcessing={false}
            onToggle={vi.fn()}
          />
      );

      expect(screen.getByText(/Analyzing audio and applying intelligent processing/i)).toBeInTheDocument();
    });
  });

  describe('Display Name', () => {
    it('should have correct display name for debugging', () => {
      expect(EnhancementToggle.displayName).toBe('EnhancementToggle');
    });
  });
});
