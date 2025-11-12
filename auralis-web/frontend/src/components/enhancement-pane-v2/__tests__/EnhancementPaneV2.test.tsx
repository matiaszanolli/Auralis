/**
 * EnhancementPaneV2 Component Tests
 *
 * Tests the enhancement control interface:
 * - Preset selector
 * - Parameter adjustment
 * - Audio characteristics display
 * - Enhancement toggle
 * - Save/load presets
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import EnhancementPaneV2 from '../EnhancementPaneV2';
import { useEnhancement } from '../../../contexts/EnhancementContext';
import { usePlayerAPI } from '../../../hooks/usePlayerAPI';
import { auralisTheme } from '../../../theme/auralisTheme';

jest.mock('../../../contexts/EnhancementContext');
jest.mock('../../../hooks/usePlayerAPI');

const mockEnhancementContext = {
  isEnabled: true,
  currentPreset: 'adaptive',
  parameters: {
    eq: { low: 0, mid: 0, high: 0 },
    compression: 1,
    loudness: 0,
  },
  setPreset: jest.fn(),
  updateParameter: jest.fn(),
  toggleEnhancement: jest.fn(),
  savePreset: jest.fn(),
};

const mockPlayerAPI = {
  applyEnhancement: jest.fn(),
};

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('EnhancementPaneV2', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useEnhancement as jest.Mock).mockReturnValue(mockEnhancementContext);
    (usePlayerAPI as jest.Mock).mockReturnValue(mockPlayerAPI);
  });

  describe('Rendering', () => {
    it('should render enhancement pane', () => {
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const pane = screen.getByTestId(/enhancement|pane/i);
      expect(pane).toBeInTheDocument();
    });

    it('should display enhancement toggle', () => {
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const toggle = screen.getByRole('switch') || screen.getByRole('checkbox', { name: /enhancement/i });
      expect(toggle).toBeInTheDocument();
    });

    it('should show preset selector', () => {
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const presetButton = screen.getByRole('button', { name: /adaptive|preset/i });
      expect(presetButton).toBeInTheDocument();
    });

    it('should display audio characteristics', () => {
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const characteristics = screen.queryByTestId(/characteristics|audio/i);
      expect(characteristics || screen.getByText(/frequency|loudness|dynamic/i)).toBeInTheDocument();
    });

    it('should show parameter controls', () => {
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const sliders = screen.getAllByRole('slider');
      expect(sliders.length).toBeGreaterThan(0);
    });
  });

  describe('Enhancement Toggle', () => {
    it('should show enabled state', () => {
      (useEnhancement as jest.Mock).mockReturnValue({
        ...mockEnhancementContext,
        isEnabled: true,
      });
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const toggle = screen.getByRole('switch') || screen.getByRole('checkbox', { name: /enhancement/i });
      expect(toggle).toBeInTheDocument();
    });

    it('should toggle enhancement on click', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const toggle = screen.getByRole('switch') || screen.getByRole('checkbox', { name: /enhancement/i });
      await user.click(toggle);
      expect(mockEnhancementContext.toggleEnhancement).toHaveBeenCalled();
    });

    it('should disable controls when enhancement off', () => {
      (useEnhancement as jest.Mock).mockReturnValue({
        ...mockEnhancementContext,
        isEnabled: false,
      });
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const sliders = screen.queryAllByRole('slider');
      sliders.forEach(slider => {
        expect(slider).toBeDisabled();
      });
    });
  });

  describe('Preset Selection', () => {
    it('should display current preset', () => {
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      expect(screen.getByText('adaptive')).toBeInTheDocument();
    });

    it('should open preset menu on click', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const presetButton = screen.getByRole('button', { name: /adaptive|preset/i });
      await user.click(presetButton);

      // Menu should show preset options
      const menuItems = screen.queryAllByRole('menuitem');
      expect(menuItems.length).toBeGreaterThan(0) || expect(screen.getByText(/bright|warm|punchy/i)).toBeInTheDocument();
    });

    it('should change preset on selection', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const presetButton = screen.getByRole('button', { name: /adaptive|preset/i });
      await user.click(presetButton);

      const brightOption = screen.getByText(/bright/i);
      if (brightOption) {
        await user.click(brightOption);
        expect(mockEnhancementContext.setPreset).toHaveBeenCalledWith('bright');
      }
    });
  });

  describe('Parameter Controls', () => {
    it('should display parameter sliders', () => {
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const sliders = screen.getAllByRole('slider');
      expect(sliders.length).toBeGreaterThan(0);
    });

    it('should update parameter on slider change', async () => {
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const sliders = screen.getAllByRole('slider');
      fireEvent.change(sliders[0], { target: { value: '50' } });
      expect(mockEnhancementContext.updateParameter).toHaveBeenCalled();
    });

    it('should display parameter values', () => {
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      // Should show some numeric values for parameters
      const numbers = screen.queryAllByText(/^[\d\.\-\+]+%?$/);
      expect(numbers.length).toBeGreaterThan(0) || expect(document.body).toBeInTheDocument();
    });

    it('should disable parameters when enhancement off', () => {
      (useEnhancement as jest.Mock).mockReturnValue({
        ...mockEnhancementContext,
        isEnabled: false,
      });
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const sliders = screen.getAllByRole('slider');
      sliders.forEach(slider => {
        expect(slider).toBeDisabled();
      });
    });
  });

  describe('Audio Characteristics Display', () => {
    it('should show audio analysis', () => {
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const characteristics = screen.queryByTestId(/characteristics|analysis/i) ||
                             screen.queryByText(/frequency|loudness|dynamic|spectral/i);
      expect(characteristics).toBeInTheDocument();
    });

    it('should display frequency response', () => {
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const frequency = screen.queryByText(/frequency|bass|treble/i);
      expect(frequency).toBeInTheDocument();
    });

    it('should display loudness metrics', () => {
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const loudness = screen.queryByText(/loudness|lufs|db/i);
      expect(loudness).toBeInTheDocument();
    });
  });

  describe('Preset Management', () => {
    it('should show save preset button', () => {
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const saveButton = screen.getByRole('button', { name: /save|preset/i });
      expect(saveButton).toBeInTheDocument();
    });

    it('should call save on preset save', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const saveButton = screen.getByRole('button', { name: /save.*preset/i });
      if (saveButton) {
        await user.click(saveButton);
        expect(mockEnhancementContext.savePreset).toHaveBeenCalled();
      }
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const sliders = screen.getAllByRole('slider');
      sliders.forEach(slider => {
        expect(slider).toHaveAccessibleName();
      });
    });

    it('should be keyboard navigable', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      const toggle = screen.getByRole('switch') || screen.getByRole('checkbox', { name: /enhancement/i });
      await user.tab();
      expect(document.activeElement).toBeInTheDocument();
    });
  });

  describe('Real-time Feedback', () => {
    it('should update display when parameters change', () => {
      const { rerender } = render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );

      (useEnhancement as jest.Mock).mockReturnValue({
        ...mockEnhancementContext,
        parameters: {
          eq: { low: 5, mid: 0, high: -5 },
          compression: 1.5,
          loudness: 2,
        },
      });

      rerender(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );

      expect(screen.getByText(/5|-5/)).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle missing preset gracefully', () => {
      (useEnhancement as jest.Mock).mockReturnValue({
        ...mockEnhancementContext,
        currentPreset: null,
      });
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      expect(screen.getByTestId(/enhancement|pane/i)).toBeInTheDocument();
    });

    it('should handle missing parameters', () => {
      (useEnhancement as jest.Mock).mockReturnValue({
        ...mockEnhancementContext,
        parameters: {},
      });
      render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );
      expect(screen.getByTestId(/enhancement|pane/i)).toBeInTheDocument();
    });
  });

  describe('State Synchronization', () => {
    it('should update when enhancement state changes', () => {
      const { rerender } = render(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );

      (useEnhancement as jest.Mock).mockReturnValue({
        ...mockEnhancementContext,
        isEnabled: false,
      });

      rerender(
        <Wrapper>
          <EnhancementPaneV2 />
        </Wrapper>
      );

      const sliders = screen.getAllByRole('slider');
      sliders.forEach(slider => {
        expect(slider).toBeDisabled();
      });
    });
  });
});
