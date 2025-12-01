/**
 * VolumeControl Component Tests
 *
 * Tests for volume slider, mute toggle, percentage display, and accessibility.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@/test/test-utils';
import VolumeControl from '../VolumeControl';

describe('VolumeControl', () => {
  describe('Basic Rendering', () => {
    it('should render all elements', () => {
      render(
        <VolumeControl
          volume={0.5}
          onVolumeChange={vi.fn()}
        />
      );

      expect(screen.getByTestId('volume-control')).toBeInTheDocument();
      expect(screen.getByTestId('volume-control-mute')).toBeInTheDocument();
      expect(screen.getByTestId('volume-control-slider')).toBeInTheDocument();
      expect(screen.getByTestId('volume-control-percentage')).toBeInTheDocument();
    });

    it('should display correct volume percentage', () => {
      render(
        <VolumeControl
          volume={0.75}
          onVolumeChange={vi.fn()}
        />
      );

      expect(screen.getByTestId('volume-control-percentage')).toHaveTextContent('75%');
    });

    it('should display 0% for zero volume', () => {
      render(
        <VolumeControl
          volume={0}
          onVolumeChange={vi.fn()}
        />
      );

      expect(screen.getByTestId('volume-control-percentage')).toHaveTextContent('0%');
    });

    it('should display 100% for max volume', () => {
      render(
        <VolumeControl
          volume={1}
          onVolumeChange={vi.fn()}
        />
      );

      expect(screen.getByTestId('volume-control-percentage')).toHaveTextContent('100%');
    });

    it('should round percentage to nearest integer', () => {
      render(
        <VolumeControl
          volume={0.666}
          onVolumeChange={vi.fn()}
        />
      );

      expect(screen.getByTestId('volume-control-percentage')).toHaveTextContent('67%');
    });
  });

  describe('Mute Icon', () => {
    it('should show muted icon when isMuted is true', () => {
      render(
        <VolumeControl
          volume={0.75}
          onVolumeChange={vi.fn()}
          isMuted={true}
        />
      );

      expect(screen.getByTestId('volume-control-icon')).toHaveTextContent('🔇');
    });

    it('should show muted icon when volume is 0 even if not muted', () => {
      render(
        <VolumeControl
          volume={0}
          onVolumeChange={vi.fn()}
          isMuted={false}
        />
      );

      expect(screen.getByTestId('volume-control-icon')).toHaveTextContent('🔇');
    });

    it('should show quiet icon for volume < 0.5', () => {
      render(
        <VolumeControl
          volume={0.25}
          onVolumeChange={vi.fn()}
          isMuted={false}
        />
      );

      expect(screen.getByTestId('volume-control-icon')).toHaveTextContent('🔈');
    });

    it('should show loud icon for volume >= 0.5', () => {
      render(
        <VolumeControl
          volume={0.75}
          onVolumeChange={vi.fn()}
          isMuted={false}
        />
      );

      expect(screen.getByTestId('volume-control-icon')).toHaveTextContent('🔊');
    });
  });

  describe('Volume Slider', () => {
    it('should update when slider value changes', () => {
      const onVolumeChange = vi.fn();
      render(
        <VolumeControl
          volume={0.5}
          onVolumeChange={onVolumeChange}
        />
      );

      const slider = screen.getByTestId('volume-control-slider') as HTMLInputElement;
      fireEvent.change(slider, { target: { value: '0.75' } });

      expect(onVolumeChange).toHaveBeenCalledWith(0.75);
    });

    it('should reflect prop changes', () => {
      const { rerender } = render(
        <VolumeControl
          volume={0.25}
          onVolumeChange={vi.fn()}
        />
      );

      const slider = screen.getByTestId('volume-control-slider') as HTMLInputElement;
      expect(slider.value).toBe('0.25');

      rerender(
        <VolumeControl
          volume={0.75}
          onVolumeChange={vi.fn()}
        />
      );

      expect(slider.value).toBe('0.75');
    });

    it('should have correct min and max attributes', () => {
      render(
        <VolumeControl
          volume={0.5}
          onVolumeChange={vi.fn()}
        />
      );

      const slider = screen.getByTestId('volume-control-slider') as HTMLInputElement;
      expect(slider.min).toBe('0');
      expect(slider.max).toBe('1');
      expect(slider.step).toBe('0.01');
    });
  });

  describe('Mute Button', () => {
    it('should call onMuteToggle when clicked', () => {
      const onMuteToggle = vi.fn();
      render(
        <VolumeControl
          volume={0.5}
          onVolumeChange={vi.fn()}
          onMuteToggle={onMuteToggle}
        />
      );

      screen.getByTestId('volume-control-mute').click();
      expect(onMuteToggle).toHaveBeenCalled();
    });

    it('should display "Unmute" label when muted', () => {
      render(
        <VolumeControl
          volume={0.75}
          onVolumeChange={vi.fn()}
          isMuted={true}
          onMuteToggle={vi.fn()}
        />
      );

      const button = screen.getByTestId('volume-control-mute');
      expect(button).toHaveAttribute('aria-label', 'Unmute');
      expect(button).toHaveAttribute('title', 'Unmute');
    });

    it('should display "Mute" label when not muted', () => {
      render(
        <VolumeControl
          volume={0.75}
          onVolumeChange={vi.fn()}
          isMuted={false}
          onMuteToggle={vi.fn()}
        />
      );

      const button = screen.getByTestId('volume-control-mute');
      expect(button).toHaveAttribute('aria-label', 'Mute');
      expect(button).toHaveAttribute('title', 'Mute');
    });
  });

  describe('Disabled State', () => {
    it('should disable mute button when disabled prop is true', () => {
      render(
        <VolumeControl
          volume={0.5}
          onVolumeChange={vi.fn()}
          disabled={true}
        />
      );

      expect(screen.getByTestId('volume-control-mute')).toBeDisabled();
    });

    it('should disable slider when disabled prop is true', () => {
      render(
        <VolumeControl
          volume={0.5}
          onVolumeChange={vi.fn()}
          disabled={true}
        />
      );

      expect(screen.getByTestId('volume-control-slider')).toBeDisabled();
    });

    it('should apply opacity when disabled', () => {
      const { container } = render(
        <VolumeControl
          volume={0.5}
          onVolumeChange={vi.fn()}
          disabled={true}
        />
      );

      const slider = screen.getByTestId('volume-control-slider');
      const styles = window.getComputedStyle(slider);
      expect(styles.opacity).toBe('0.5');
    });
  });

  describe('Accessibility', () => {
    it('should have proper aria-label on slider', () => {
      render(
        <VolumeControl
          volume={0.75}
          onVolumeChange={vi.fn()}
          isMuted={false}
        />
      );

      const slider = screen.getByTestId('volume-control-slider');
      expect(slider).toHaveAttribute('aria-label');
      expect(slider.getAttribute('aria-label')).toContain('75%');
    });

    it('should indicate muted state in aria-label', () => {
      render(
        <VolumeControl
          volume={0.75}
          onVolumeChange={vi.fn()}
          isMuted={true}
        />
      );

      const slider = screen.getByTestId('volume-control-slider');
      expect(slider.getAttribute('aria-label')).toContain('muted');
    });

    it('should support custom aria-label', () => {
      render(
        <VolumeControl
          volume={0.5}
          onVolumeChange={vi.fn()}
          ariaLabel="Custom volume label"
        />
      );

      const slider = screen.getByTestId('volume-control-slider');
      expect(slider).toHaveAttribute('aria-label', 'Custom volume label');
    });

    it('should have title attribute on slider', () => {
      render(
        <VolumeControl
          volume={0.5}
          onVolumeChange={vi.fn()}
        />
      );

      const slider = screen.getByTestId('volume-control-slider');
      expect(slider).toHaveAttribute('title', 'Volume: 50%');
    });
  });

  describe('CSS & Styling', () => {
    it('should accept custom className', () => {
      const { container } = render(
        <VolumeControl
          volume={0.5}
          onVolumeChange={vi.fn()}
          className="custom-volume-class"
        />
      );

      expect(container.querySelector('.custom-volume-class')).toBeInTheDocument();
    });

    it('should apply design tokens to container', () => {
      render(
        <VolumeControl
          volume={0.5}
          onVolumeChange={vi.fn()}
        />
      );

      const container = screen.getByTestId('volume-control');
      const styles = window.getComputedStyle(container);
      expect(styles.display).toBe('flex');
      expect(styles.alignItems).toBe('center');
    });

    it('should have proper test IDs', () => {
      render(
        <VolumeControl
          volume={0.5}
          onVolumeChange={vi.fn()}
        />
      );

      expect(screen.getByTestId('volume-control')).toBeInTheDocument();
      expect(screen.getByTestId('volume-control-mute')).toBeInTheDocument();
      expect(screen.getByTestId('volume-control-slider')).toBeInTheDocument();
      expect(screen.getByTestId('volume-control-icon')).toBeInTheDocument();
      expect(screen.getByTestId('volume-control-percentage')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should clamp negative volume to 0', () => {
      render(
        <VolumeControl
          volume={-0.5}
          onVolumeChange={vi.fn()}
        />
      );

      const slider = screen.getByTestId('volume-control-slider') as HTMLInputElement;
      expect(slider.value).toBe('0');
      expect(screen.getByTestId('volume-control-percentage')).toHaveTextContent('0%');
    });

    it('should clamp over-1 volume to 1', () => {
      render(
        <VolumeControl
          volume={1.5}
          onVolumeChange={vi.fn()}
        />
      );

      const slider = screen.getByTestId('volume-control-slider') as HTMLInputElement;
      expect(slider.value).toBe('1');
      expect(screen.getByTestId('volume-control-percentage')).toHaveTextContent('100%');
    });

    it('should handle NaN volume as 0%', () => {
      render(
        <VolumeControl
          volume={NaN}
          onVolumeChange={vi.fn()}
        />
      );

      expect(screen.getByTestId('volume-control-percentage')).toHaveTextContent('0%');
    });

    it('should handle Infinity volume as 100%', () => {
      render(
        <VolumeControl
          volume={Infinity}
          onVolumeChange={vi.fn()}
        />
      );

      expect(screen.getByTestId('volume-control-percentage')).toHaveTextContent('100%');
    });
  });

  describe('Realistic Scenarios', () => {
    it('should handle volume adjustment sequence', () => {
      const onVolumeChange = vi.fn();
      const { rerender } = render(
        <VolumeControl
          volume={0.2}
          onVolumeChange={onVolumeChange}
        />
      );

      expect(screen.getByTestId('volume-control-percentage')).toHaveTextContent('20%');

      const slider = screen.getByTestId('volume-control-slider') as HTMLInputElement;
      fireEvent.change(slider, { target: { value: '0.5' } });

      expect(onVolumeChange).toHaveBeenCalledWith(0.5);

      rerender(
        <VolumeControl
          volume={0.5}
          onVolumeChange={onVolumeChange}
        />
      );

      expect(screen.getByTestId('volume-control-percentage')).toHaveTextContent('50%');
    });

    it('should handle mute and unmute sequence', () => {
      const onMuteToggle = vi.fn();
      const { rerender } = render(
        <VolumeControl
          volume={0.75}
          onVolumeChange={vi.fn()}
          isMuted={false}
          onMuteToggle={onMuteToggle}
        />
      );

      expect(screen.getByTestId('volume-control-icon')).toHaveTextContent('🔊');

      screen.getByTestId('volume-control-mute').click();
      expect(onMuteToggle).toHaveBeenCalled();

      rerender(
        <VolumeControl
          volume={0.75}
          onVolumeChange={vi.fn()}
          isMuted={true}
          onMuteToggle={onMuteToggle}
        />
      );

      expect(screen.getByTestId('volume-control-icon')).toHaveTextContent('🔇');

      screen.getByTestId('volume-control-mute').click();
      expect(onMuteToggle).toHaveBeenCalledTimes(2);
    });
  });
});
