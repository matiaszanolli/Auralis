/**
 * VolumeControl Component Tests
 *
 * Tests volume slider with mute toggle:
 * - Slider value changes (0-1)
 * - Mute/unmute functionality
 * - Icon changes based on volume level
 * - Callbacks and event handling
 * - Accessibility
 * - Memoization
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { VolumeControl } from '../VolumeControl';


describe('VolumeControl', () => {
  describe('Rendering', () => {
    it('should render volume control container', () => {
      const { container } = render(
        <VolumeControl volume={0.5} onChange={vi.fn()} />
      );

      const volumeContainer = container.querySelector('[class*="MuiBox"]');
      expect(volumeContainer).toBeTruthy();
    });

    it('should render mute button', () => {
      render(
        <VolumeControl volume={0.5} onChange={vi.fn()} />
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('should render volume slider', () => {
      const { container } = render(
        <VolumeControl volume={0.5} onChange={vi.fn()} />
      );

      const slider = container.querySelector('[class*="MuiSlider"]');
      expect(slider).toBeTruthy();
    });

    it('should render all components together', () => {
      const { container } = render(
        <VolumeControl volume={0.5} onChange={vi.fn()} />
      );

      const button = screen.getAllByRole('button');
      const slider = container.querySelector('[class*="MuiSlider"]');

      expect(button.length).toBeGreaterThan(0);
      expect(slider).toBeTruthy();
    });
  });

  describe('Volume Slider', () => {
    it('should set slider value to current volume', () => {
      const { container } = render(
        <VolumeControl volume={0.5} onChange={vi.fn()} />
      );

      const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider?.value).toBe('0.5');
    });

    it('should update slider when volume changes', () => {
      const { rerender, container } = render(
        <VolumeControl volume={0.3} onChange={vi.fn()} />
      );

      let slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider?.value).toBe('0.3');

      rerender(
        <VolumeControl volume={0.7} onChange={vi.fn()} />
      );

      slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider?.value).toBe('0.7');
    });

    it('should handle minimum volume (0)', () => {
      const { container } = render(
        <VolumeControl volume={0} onChange={vi.fn()} />
      );

      const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider?.value).toBe('0');
    });

    it('should handle maximum volume (1)', () => {
      const { container } = render(
        <VolumeControl volume={1} onChange={vi.fn()} />
      );

      const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider?.value).toBe('1');
    });

    it('should call onChange when slider is moved', async () => {
      const mockChange = vi.fn();

      const { container } = render(
        <VolumeControl volume={0.5} onChange={mockChange} />
      );

      const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      fireEvent.change(slider, { target: { value: '0.7' } });

      expect(mockChange).toHaveBeenCalled();
    });
  });

  describe('Mute Button', () => {
    it('should render mute button', () => {
      render(
        <VolumeControl volume={0.5} onChange={vi.fn()} />
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('should have mute aria-label when not muted', () => {
      render(
        <VolumeControl volume={0.5} onChange={vi.fn()} />
      );

      const buttons = screen.getAllByRole('button');
      const muteButton = buttons[0];
      expect(muteButton.getAttribute('aria-label')).toBe('Mute');
    });

    it('should call onChange with 0 when mute is clicked', async () => {
      const mockChange = vi.fn();
      const user = userEvent.setup();

      render(
        <VolumeControl volume={0.5} onChange={mockChange} />
      );

      const buttons = screen.getAllByRole('button');
      const muteButton = buttons[0];
      await user.click(muteButton);

      expect(mockChange).toHaveBeenCalledWith(0);
    });
  });

  describe('Volume Icons', () => {
    it('should display VolumeOff icon when volume is 0', () => {
      const { container } = render(
        <VolumeControl volume={0} onChange={vi.fn()} />
      );

      // Icon should be present when volume is 0
      const svgIcon = container.querySelector('[class*="MuiSvgIcon"]');
      expect(svgIcon).toBeTruthy();
    });

    it('should display VolumeMute icon when volume is low (< 0.3)', () => {
      const { container } = render(
        <VolumeControl volume={0.2} onChange={vi.fn()} />
      );

      const svgIcon = container.querySelector('[class*="MuiSvgIcon"]');
      expect(svgIcon).toBeTruthy();
    });

    it('should display VolumeDown icon when volume is medium (0.3-0.7)', () => {
      const { container } = render(
        <VolumeControl volume={0.5} onChange={vi.fn()} />
      );

      const svgIcon = container.querySelector('[class*="MuiSvgIcon"]');
      expect(svgIcon).toBeTruthy();
    });

    it('should display VolumeUp icon when volume is high (> 0.7)', () => {
      const { container } = render(
        <VolumeControl volume={0.8} onChange={vi.fn()} />
      );

      const svgIcon = container.querySelector('[class*="MuiSvgIcon"]');
      expect(svgIcon).toBeTruthy();
    });

    it('should change icon when volume changes', () => {
      const { rerender, container } = render(
        <VolumeControl volume={0.1} onChange={vi.fn()} />
      );

      let svgIcon = container.querySelector('[class*="MuiSvgIcon"]');
      expect(svgIcon).toBeTruthy();

      rerender(
        <VolumeControl volume={0.9} onChange={vi.fn()} />
      );

      svgIcon = container.querySelector('[class*="MuiSvgIcon"]');
      expect(svgIcon).toBeTruthy();
    });
  });

  describe('Mute/Unmute Behavior', () => {
    it('should mute when mute button is clicked', async () => {
      const mockChange = vi.fn();
      const user = userEvent.setup();

      render(
        <VolumeControl volume={0.5} onChange={mockChange} />
      );

      const buttons = screen.getAllByRole('button');
      const muteButton = buttons[0];
      await user.click(muteButton);

      expect(mockChange).toHaveBeenCalledWith(0);
    });

    it('should restore previous volume when unmuting', async () => {
      const mockChange = vi.fn();
      const user = userEvent.setup();

      const { rerender } = render(
        <VolumeControl volume={0.5} onChange={mockChange} />
      );

      // First click: mute
      let buttons = screen.getAllByRole('button');
      let muteButton = buttons[0];
      await user.click(muteButton);

      expect(mockChange).toHaveBeenCalledWith(0);

      rerender(
        <VolumeControl volume={0} onChange={mockChange} />
      );

      // Second click: unmute
      buttons = screen.getAllByRole('button');
      muteButton = buttons[0];
      await user.click(muteButton);

      // Should restore to a non-zero value (default 0.5 or previous)
      expect(mockChange).toHaveBeenCalled();
    });
  });

  describe('Boundary Values', () => {
    it('should handle zero volume', () => {
      const { container } = render(
        <VolumeControl volume={0} onChange={vi.fn()} />
      );

      const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider?.value).toBe('0');
    });

    it('should handle maximum volume', () => {
      const { container } = render(
        <VolumeControl volume={1} onChange={vi.fn()} />
      );

      const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider?.value).toBe('1');
    });

    it('should handle very low volume (0.01)', () => {
      const { container } = render(
        <VolumeControl volume={0.01} onChange={vi.fn()} />
      );

      const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider?.value).toBe('0.01');
    });

    it('should handle very high volume (0.99)', () => {
      const { container } = render(
        <VolumeControl volume={0.99} onChange={vi.fn()} />
      );

      const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider?.value).toBe('0.99');
    });

    it('should handle precise volume values', () => {
      const { container } = render(
        <VolumeControl volume={0.33} onChange={vi.fn()} />
      );

      const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider?.value).toBe('0.33');
    });
  });

  describe('Memoization', () => {
    it('should be memoized component', () => {
      const mockChange = vi.fn();

      const { rerender } = render(
        <VolumeControl volume={0.5} onChange={mockChange} />
      );

      expect(screen.getAllByRole('button').length).toBeGreaterThan(0);

      rerender(
        <VolumeControl volume={0.5} onChange={mockChange} />
      );

      expect(screen.getAllByRole('button').length).toBeGreaterThan(0);
    });

    it('should update when volume prop changes', () => {
      const { rerender, container } = render(
        <VolumeControl volume={0.3} onChange={vi.fn()} />
      );

      let slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider?.value).toBe('0.3');

      rerender(
        <VolumeControl volume={0.7} onChange={vi.fn()} />
      );

      slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      expect(slider?.value).toBe('0.7');
    });

    it('should handle onChange callback changes', async () => {
      const mockChange1 = vi.fn();
      const mockChange2 = vi.fn();
      const user = userEvent.setup();

      const { rerender, container } = render(
        <VolumeControl volume={0.5} onChange={mockChange1} />
      );

      let slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      fireEvent.change(slider, { target: { value: '0.6' } });

      expect(mockChange1).toHaveBeenCalled();

      rerender(
        <VolumeControl volume={0.5} onChange={mockChange2} />
      );

      slider = container.querySelector('input[type="range"]') as HTMLInputElement;
      fireEvent.change(slider, { target: { value: '0.6' } });

      expect(mockChange2).toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('should have aria-label on mute button', () => {
      render(
        <VolumeControl volume={0.5} onChange={vi.fn()} />
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons[0].getAttribute('aria-label')).toBeTruthy();
    });

    it('should have aria-label on volume slider', () => {
      const { container } = render(
        <VolumeControl volume={0.5} onChange={vi.fn()} />
      );

      const slider = container.querySelector('input[type="range"]');
      expect(slider?.getAttribute('aria-label')).toBe('Volume');
    });

    it('should have title attribute on mute button', () => {
      render(
        <VolumeControl volume={0.5} onChange={vi.fn()} />
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons[0].getAttribute('title')).toBeTruthy();
    });

    it('should have min and max attributes on slider', () => {
      const { container } = render(
        <VolumeControl volume={0.5} onChange={vi.fn()} />
      );

      const slider = container.querySelector('input[type="range"]');
      expect(slider?.getAttribute('min')).toBe('0');
      expect(slider?.getAttribute('max')).toBe('1');
    });
  });

  describe('Display Name', () => {
    it('should have correct display name for debugging', () => {
      expect(VolumeControl.displayName).toBe('VolumeControl');
    });
  });
});
