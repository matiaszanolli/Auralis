
import { SettingsUpdate } from '@/services/settingsService';
import { SettingsDialogContent as StyledContent } from './SettingsDialog.styles';
import { LibrarySettingsPanel } from './LibrarySettingsPanel';
import { PlaybackSettingsPanel } from './PlaybackSettingsPanel';
import { AudioSettingsPanel } from './AudioSettingsPanel';
import { InterfaceSettingsPanel } from './InterfaceSettingsPanel';
import { EnhancementSettingsPanel } from './EnhancementSettingsPanel';
import { AdvancedSettingsPanel } from './AdvancedSettingsPanel';

interface SettingsDialogContentProps {
  activeTab: number;
  /**
   * Mirrors `useSettingsDialog().getValue` exactly (#5638): the `| null` is
   * load-bearing. It was `=> any` here, which erased the null the hook
   * returns while settings are unloaded (or a stored value is null) and let
   * nulls reach these panels' controlled MUI Select/Switch/Slider props
   * unchecked — the type-level root cause behind #5517. Every call site
   * below decides its null fallback explicitly.
   */
  getValue: <K extends keyof SettingsUpdate>(key: K) => SettingsUpdate[K] | null;
  onSettingChange: (key: keyof SettingsUpdate, value: SettingsUpdate[keyof SettingsUpdate]) => void;
  onAddFolder: () => Promise<void>;
  onRemoveFolder: (folder: string) => void;
  onScanNow: () => void;
}

/**
 * SettingsDialogContent - Content area with tab panels
 *
 * Displays the appropriate settings panel based on active tab.
 */
export const SettingsDialogContentComponent = ({
  activeTab,
  getValue,
  onSettingChange,
  onAddFolder,
  onRemoveFolder,
  onScanNow,
}: SettingsDialogContentProps) => {
  return (
    <StyledContent>
      {activeTab === 0 && (
        <LibrarySettingsPanel
          scanFolders={getValue('scan_folders') ?? []}
          autoScan={getValue('auto_scan') ?? false}
          scanInterval={getValue('scan_interval') ?? 3600} // backend's own null fallback (library_auto_scanner)
          onSettingChange={onSettingChange}
          onAddFolder={onAddFolder}
          onRemoveFolder={onRemoveFolder}
          onScanNow={onScanNow}
        />
      )}

      {activeTab === 1 && (
        <PlaybackSettingsPanel
          gaplessEnabled={getValue('gapless_enabled') ?? false}
          crossfadeEnabled={getValue('crossfade_enabled') ?? false}
          crossfadeDuration={getValue('crossfade_duration') ?? 0}
          replayGainEnabled={getValue('replay_gain_enabled') ?? false}
          volume={getValue('volume') ?? 0.8} // the backend's normalised default (settings.py)
          onSettingChange={onSettingChange}
        />
      )}

      {activeTab === 2 && (
        <AudioSettingsPanel
          outputDevice={getValue('output_device') ?? 'default'}
          bitDepth={getValue('bit_depth') ?? 16}
          sampleRate={getValue('sample_rate') ?? 44100}
          onSettingChange={onSettingChange}
        />
      )}

      {activeTab === 3 && (
        <InterfaceSettingsPanel
          showVisualizations={getValue('show_visualizations') ?? true}
          miniPlayerOnClose={getValue('mini_player_on_close') ?? false}
          onSettingChange={onSettingChange}
        />
      )}

      {activeTab === 4 && (
        <EnhancementSettingsPanel
          // The intensity can still arrive as null (#5517), and nothing is loaded
          // before the first fetch: fall back to the defaults the panel's single
          // Select option implies, mirroring the scanFolders ?? [] guard above.
          defaultPreset={getValue('default_preset') ?? 'adaptive'}
          autoEnhance={getValue('auto_enhance') ?? false}
          enhancementIntensity={getValue('enhancement_intensity') ?? 1.0}
          onSettingChange={onSettingChange}
        />
      )}

      {activeTab === 5 && (
        <AdvancedSettingsPanel
          cacheSize={getValue('cache_size') ?? 1024}
          maxConcurrentScans={getValue('max_concurrent_scans') ?? 4}
          enableAnalytics={getValue('enable_analytics') ?? false}
          debugMode={getValue('debug_mode') ?? false}
          onSettingChange={onSettingChange}
        />
      )}
    </StyledContent>
  );
};

export default SettingsDialogContentComponent;
