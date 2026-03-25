/**
 * EnhancementToggle Component Tests
 *
 * Tests for both button and switch variants, covering rendering,
 * toggle behavior, processing state, and description display.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@/test/test-utils';
import { EnhancementToggle } from '../EnhancementToggle';

describe('EnhancementToggle', () => {
  describe('Button variant', () => {
    it('should render the button variant by default', () => {
      const onToggle = vi.fn();
      render(<EnhancementToggle isEnabled={false} onToggle={onToggle} />);

      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('should show "Enhanced" label when enabled', () => {
      const onToggle = vi.fn();
      render(<EnhancementToggle isEnabled={true} onToggle={onToggle} variant="button" />);

      expect(screen.getByText('Enhanced')).toBeInTheDocument();
    });

    it('should show "Original" label when disabled', () => {
      const onToggle = vi.fn();
      render(<EnhancementToggle isEnabled={false} onToggle={onToggle} variant="button" />);

      expect(screen.getByText('Original')).toBeInTheDocument();
    });

    it('should call onToggle with true when clicking while disabled', () => {
      const onToggle = vi.fn();
      render(<EnhancementToggle isEnabled={false} onToggle={onToggle} variant="button" />);

      fireEvent.click(screen.getByRole('button'));
      expect(onToggle).toHaveBeenCalledWith(true);
    });

    it('should call onToggle with false when clicking while enabled', () => {
      const onToggle = vi.fn();
      render(<EnhancementToggle isEnabled={true} onToggle={onToggle} variant="button" />);

      fireEvent.click(screen.getByRole('button'));
      expect(onToggle).toHaveBeenCalledWith(false);
    });
  });

  describe('Switch variant', () => {
    it('should render a switch control', () => {
      const onToggle = vi.fn();
      render(
        <EnhancementToggle isEnabled={false} onToggle={onToggle} variant="switch" />
      );

      expect(screen.getByRole('checkbox')).toBeInTheDocument();
    });

    it('should call onToggle when switch is toggled', () => {
      const onToggle = vi.fn();
      render(
        <EnhancementToggle isEnabled={false} onToggle={onToggle} variant="switch" />
      );

      fireEvent.click(screen.getByRole('checkbox'));
      expect(onToggle).toHaveBeenCalledWith(true);
    });

    it('should be disabled when isProcessing is true', () => {
      const onToggle = vi.fn();
      render(
        <EnhancementToggle
          isEnabled={false}
          onToggle={onToggle}
          variant="switch"
          isProcessing={true}
        />
      );

      expect(screen.getByRole('checkbox')).toBeDisabled();
    });

    it('should show default description when enabled and showDescription is true', () => {
      const onToggle = vi.fn();
      render(
        <EnhancementToggle
          isEnabled={true}
          onToggle={onToggle}
          variant="switch"
          showDescription={true}
        />
      );

      expect(
        screen.getByText('Analyzing audio and applying intelligent processing')
      ).toBeInTheDocument();
    });

    it('should show default description when disabled and showDescription is true', () => {
      const onToggle = vi.fn();
      render(
        <EnhancementToggle
          isEnabled={false}
          onToggle={onToggle}
          variant="switch"
          showDescription={true}
        />
      );

      expect(
        screen.getByText('Turn on to enhance your music automatically')
      ).toBeInTheDocument();
    });

    it('should show custom description when provided', () => {
      const onToggle = vi.fn();
      render(
        <EnhancementToggle
          isEnabled={false}
          onToggle={onToggle}
          variant="switch"
          showDescription={true}
          description="Custom description text"
        />
      );

      expect(screen.getByText('Custom description text')).toBeInTheDocument();
    });

    it('should not show description when showDescription is false', () => {
      const onToggle = vi.fn();
      render(
        <EnhancementToggle
          isEnabled={true}
          onToggle={onToggle}
          variant="switch"
          showDescription={false}
        />
      );

      expect(
        screen.queryByText('Analyzing audio and applying intelligent processing')
      ).not.toBeInTheDocument();
    });
  });
});
