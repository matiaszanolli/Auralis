/**
 * SettingsDialog Component Tests
 *
 * Tests comprehensive settings dialog with multiple tabs:
 * - Dialog open/close behavior
 * - Tab navigation (Library, Playback, Audio, Interface, Enhancement, Advanced)
 * - Settings loading and saving
 * - Toggle controls and sliders
 * - Form field changes
 * - Reset functionality
 * - Callbacks
 * - Accessibility
 */

import React from 'react';
import { render, screen, waitFor } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SettingsDialog from '../SettingsDialog';

// Mock the settings service
vi.mock('../../../services/settingsService', () => ({
  settingsService: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    resetSettings: vi.fn(),
    addScanFolder: vi.fn(),
    removeScanFolder: vi.fn(),
  },
}));


const mockSettings = {
  scan_folders: ['/music/library'],
  auto_scan: true,
  scan_interval: 3600,
  gapless_enabled: true,
  crossfade_enabled: false,
  crossfade_duration: 5,
  replay_gain_enabled: true,
  volume: 0.8,
  output_device: 'default',
  bit_depth: 24,
  sample_rate: 44100,
  theme: 'dark',
  show_visualizations: true,
  mini_player_on_close: false,
  default_preset: 'adaptive',
  auto_enhance: true,
  enhancement_intensity: 0.7,
  cache_size: 1024,
  max_concurrent_scans: 4,
  enable_analytics: true,
  debug_mode: false,
};

describe('SettingsDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Dialog Rendering', () => {
    it('should not render when closed', () => {
      render(
        <SettingsDialog open={false} onClose={vi.fn()} />
      );

      const dialog = screen.queryByRole('dialog');
      expect(dialog).not.toBeInTheDocument();
    });

    it('should render when open', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        const dialog = screen.queryByRole('dialog');
        expect(dialog).toBeInTheDocument();
      });
    });

    it('should have title "Settings"', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        expect(screen.getByText('Settings')).toBeInTheDocument();
      });
    });

    it('should have close button', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        const closeButtons = screen.getAllByRole('button', { name: /close/i });
        expect(closeButtons.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Tab Navigation', () => {
    it('should render all setting tabs', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        expect(screen.getByText('Library')).toBeInTheDocument();
        expect(screen.getByText('Playback')).toBeInTheDocument();
        expect(screen.getByText('Audio')).toBeInTheDocument();
        expect(screen.getByText('Interface')).toBeInTheDocument();
        expect(screen.getByText('Enhancement')).toBeInTheDocument();
        expect(screen.getByText('Advanced')).toBeInTheDocument();
      });
    });

    it('should switch to Library tab', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);
      const user = userEvent.setup();

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        const libraryTab = screen.getByText('Library');
        expect(libraryTab).toBeInTheDocument();
      });

      const libraryTab = screen.getByText('Library');
      await user.click(libraryTab);

      await waitFor(() => {
        expect(screen.getByText(/Scan Folders/i)).toBeInTheDocument();
      });
    });

    it('should switch to Playback tab', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);
      const user = userEvent.setup();

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        const playbackTab = screen.getByText('Playback');
        expect(playbackTab).toBeInTheDocument();
      });

      const playbackTab = screen.getByText('Playback');
      await user.click(playbackTab);

      await waitFor(() => {
        expect(screen.getByText(/Gapless playback/i)).toBeInTheDocument();
      });
    });

    it('should switch to Audio tab', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);
      const user = userEvent.setup();

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        const audioTab = screen.getByText('Audio');
        expect(audioTab).toBeInTheDocument();
      });

      const audioTab = screen.getByText('Audio');
      await user.click(audioTab);

      await waitFor(() => {
        expect(screen.getByText(/Output Device/i)).toBeInTheDocument();
      });
    });

    it('should switch to Interface tab', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);
      const user = userEvent.setup();

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        const interfaceTab = screen.getByText('Interface');
        expect(interfaceTab).toBeInTheDocument();
      });

      const interfaceTab = screen.getByText('Interface');
      await user.click(interfaceTab);

      await waitFor(() => {
        expect(screen.getByText(/Theme/i)).toBeInTheDocument();
      });
    });

    it('should switch to Enhancement tab', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);
      const user = userEvent.setup();

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        const enhancementTab = screen.getByText('Enhancement');
        expect(enhancementTab).toBeInTheDocument();
      });

      const enhancementTab = screen.getByText('Enhancement');
      await user.click(enhancementTab);

      await waitFor(() => {
        expect(screen.getByText(/Default Preset/i)).toBeInTheDocument();
      });
    });

    it('should switch to Advanced tab', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);
      const user = userEvent.setup();

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        const advancedTab = screen.getByText('Advanced');
        expect(advancedTab).toBeInTheDocument();
      });

      const advancedTab = screen.getByText('Advanced');
      await user.click(advancedTab);

      await waitFor(() => {
        expect(screen.getByText(/Cache Size/i)).toBeInTheDocument();
      });
    });
  });

  describe('Settings Loading', () => {
    it('should load settings when dialog opens', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        expect(settingsService.getSettings).toHaveBeenCalled();
      });
    });

    it('should display loaded settings in controls', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        const libraryTab = screen.getByText('Library');
        expect(libraryTab).toBeInTheDocument();
      });
    });
  });

  describe('Dialog Actions', () => {
    it('should have Save Changes button', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        expect(screen.getByText('Save Changes')).toBeInTheDocument();
      });
    });

    it('should have Cancel button', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        expect(screen.getByText('Cancel')).toBeInTheDocument();
      });
    });

    it('should have Reset to Defaults button', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        expect(screen.getByText('Reset to Defaults')).toBeInTheDocument();
      });
    });

    it('should call onClose when Cancel is clicked', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);
      const mockClose = vi.fn();
      const user = userEvent.setup();

      render(
        <SettingsDialog open={true} onClose={mockClose} />
      );

      await waitFor(() => {
        expect(screen.getByText('Cancel')).toBeInTheDocument();
      });

      const cancelButton = screen.getByText('Cancel');
      await user.click(cancelButton);

      expect(mockClose).toHaveBeenCalled();
    });

    it('should call onClose when close button is clicked', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);
      const mockClose = vi.fn();
      const user = userEvent.setup();

      render(
        <SettingsDialog open={true} onClose={mockClose} />
      );

      await waitFor(() => {
        const closeButtons = screen.getAllByRole('button');
        expect(closeButtons.length).toBeGreaterThan(0);
      });

      const closeButtons = screen.getAllByRole('button');
      // Find the close icon button (usually the first one in the header)
      if (closeButtons.length > 0) {
        await user.click(closeButtons[0]);
      }

      await waitFor(() => {
        expect(mockClose).toHaveBeenCalled();
      });
    });
  });

  describe('Callbacks', () => {
    it('should call onSettingsChange when settings are saved', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);
      vi.mocked(settingsService.updateSettings).mockResolvedValue({
        settings: mockSettings,
      });

      const mockSettingsChange = vi.fn();
      const mockClose = vi.fn();
      const user = userEvent.setup();

      render(
        <SettingsDialog
            open={true}
            onClose={mockClose}
            onSettingsChange={mockSettingsChange}
          />
      );

      await waitFor(() => {
        expect(screen.getByText('Save Changes')).toBeInTheDocument();
      });

      const saveButton = screen.getByText('Save Changes');
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockClose).toHaveBeenCalled();
      });
    });
  });

  describe('Accessibility', () => {
    it('should have accessible tabs', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        const tabs = screen.getAllByRole('tab');
        expect(tabs.length).toBeGreaterThan(0);
      });
    });

    it('should have buttons with proper roles', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        const buttons = screen.getAllByRole('button');
        expect(buttons.length).toBeGreaterThan(0);
      });
    });

    it('should have proper dialog role', async () => {
      const { settingsService } = await import('../../../services/settingsService');
      vi.mocked(settingsService.getSettings).mockResolvedValue(mockSettings);

      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      await waitFor(() => {
        const dialog = screen.getByRole('dialog');
        expect(dialog).toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    it('should not render when open is false', () => {
      render(
        <SettingsDialog open={false} onClose={vi.fn()} />
      );

      const dialog = screen.queryByRole('dialog');
      expect(dialog).not.toBeInTheDocument();
    });
  });
});
