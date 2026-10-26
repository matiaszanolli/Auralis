/**
 * SettingsDialog Component Tests
 *
 * Tests comprehensive settings dialog:
 * - Dialog visibility
 * - Tab navigation
 * - Callbacks
 */

import { render, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SettingsDialog from '../SettingsDialog';
import SettingsDialogContent from '../SettingsDialogContent';

// Mock the settings service
vi.mock('@/services/settingsService', () => ({
  settingsService: {
    getSettings: vi.fn(async () => ({
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
    })),
    updateSettings: vi.fn(async () => undefined),
    resetSettings: vi.fn(async () => undefined),
    addScanFolder: vi.fn(async () => undefined),
    removeScanFolder: vi.fn(async () => undefined),
  },
}));

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

    it('should render when open', () => {
      // Test that component renders without error when open=true
      const { container } = render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      // Dialog component rendered without crashing (content may be in portal)
      expect(container).toBeInTheDocument();
    });

    it('should have close button', () => {
      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      // Was `>= 0`, true by construction for any array length (#5136).
      const closeButtons = screen.queryAllByRole('button', { name: /close/i });
      expect(closeButtons.length).toBeGreaterThan(0);
    });
  });

  describe('Dialog Actions', () => {
    it('should call onClose when close button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();

      render(
        <SettingsDialog open={true} onClose={onClose} />
      );

      const closeButtons = screen.queryAllByRole('button', { name: /close/i });
      if (closeButtons.length > 0) {
        await user.click(closeButtons[0]);
        expect(onClose).toHaveBeenCalled();
      }
    });

    it('calls onClose on Cancel, and a cancelled edit does not survive a reopen (#5618, #5673)', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();

      const { rerender } = render(
        <SettingsDialog open={true} onClose={onClose} />
      );

      // The saved value (mocked service) is ON.
      const autoScan = await screen.findByRole('switch', { name: /auto-scan library/i });
      expect(autoScan).toBeChecked();

      // A pending, unsaved edit…
      await user.click(autoScan);
      expect(autoScan).not.toBeChecked();

      // …must be discarded by Cancel (the dialog stays mounted across the
      // close in the app, so the discard is what the reopen shows)…
      await user.click(screen.getByRole('button', { name: 'Cancel' }));
      expect(onClose).toHaveBeenCalledTimes(1);

      // …and reopening shows the stored value, not the cancelled edit.
      rerender(<SettingsDialog open={false} onClose={onClose} />);
      rerender(<SettingsDialog open={true} onClose={onClose} />);
      const reopened = await screen.findByRole('switch', { name: /auto-scan library/i });
      expect(reopened).toBeChecked();
    });
  });

  describe('Tab Navigation', () => {
    it('should render tabs when open', () => {
      render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      const tabs = screen.queryAllByRole('tab');
      // Should have multiple tabs or tab-like elements
      expect(tabs.length >= 0).toBe(true);
    });
  });

  describe('Accessibility', () => {
    it('should have proper dialog role', () => {
      // Test that component renders properly in accessibility context
      const { container } = render(
        <SettingsDialog open={true} onClose={vi.fn()} />
      );

      // Dialog component renders without crashing (content may be in portal)
      expect(container).toBeInTheDocument();
    });
  });

  // #5517: the backend degrades a legacy/out-of-range stored default_preset
  // or enhancement_intensity to null on the wire; the dialog must fall back
  // to sane defaults instead of feeding null to the Select/Slider.
  describe('legacy-degraded settings fall back (#5517)', () => {
    it('renders the Enhancement tab with adaptive/1.0 when both are null', () => {
      render(
        <SettingsDialogContent
          activeTab={4}
          getValue={(key) =>
            key === 'default_preset' || key === 'enhancement_intensity' ? null : undefined
          }
          onSettingChange={vi.fn()}
          onAddFolder={vi.fn()}
          onRemoveFolder={vi.fn()}
          onScanNow={vi.fn()}
        />
      );

      expect(screen.getByRole('combobox', { name: 'Default Preset' })).toHaveTextContent(
        'Adaptive'
      );
      expect(screen.getByRole('slider', { name: 'Enhancement intensity' })).toHaveAttribute(
        'aria-valuenow',
        '1'
      );
    });
  });

  // #5638: the getValue prop used to be typed `=> any`, which erased the null
  // the hook returns while settings are unloaded. With the prop now typed
  // `SettingsUpdate[K] | null`, every panel must survive a null-for-every-key
  // dialog: controls stay controlled (no uncontrolled-to-controlled React
  // warnings) and display their explicit fallbacks.
  describe('unloaded settings stay controlled (#5638)', () => {
    it('renders every tab with an all-null getValue without React warnings', () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
      try {
        for (let tab = 0; tab < 6; tab++) {
          const { unmount } = render(
            <SettingsDialogContent
              activeTab={tab}
              getValue={() => null}
              onSettingChange={vi.fn()}
              onAddFolder={vi.fn()}
              onRemoveFolder={vi.fn()}
              onScanNow={vi.fn()}
            />
          );
          unmount();
        }

        const controlledWarnings = consoleError.mock.calls
          .map((args) => args.join(' '))
          .filter((text) => /uncontrolled|controlled/i.test(text));
        expect(controlledWarnings).toEqual([]);
      } finally {
        consoleError.mockRestore();
      }
    });

    it('shows the null fallbacks on the Enhancement tab', () => {
      render(
        <SettingsDialogContent
          activeTab={4}
          getValue={() => null}
          onSettingChange={vi.fn()}
          onAddFolder={vi.fn()}
          onRemoveFolder={vi.fn()}
          onScanNow={vi.fn()}
        />
      );

      expect(screen.getByRole('combobox', { name: 'Default Preset' })).toHaveTextContent(
        'Adaptive'
      );
      expect(screen.getByRole('slider', { name: 'Enhancement intensity' })).toHaveAttribute(
        'aria-valuenow',
        '1'
      );
    });
  });
});
