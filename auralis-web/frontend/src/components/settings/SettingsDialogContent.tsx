import React from 'react';
import { SettingsUpdate } from '../../services/settingsService';
import { SettingsDialogContent as StyledContent } from './SettingsDialog.styles';
import { LibrarySettingsPanel } from './LibrarySettingsPanel';
import { PlaybackSettingsPanel } from './PlaybackSettingsPanel';
import { AudioSettingsPanel } from './AudioSettingsPanel';
import { InterfaceSettingsPanel } from './InterfaceSettingsPanel';
import { EnhancementSettingsPanel } from './EnhancementSettingsPanel';
import { AdvancedSettingsPanel } from './AdvancedSettingsPanel';

interface SettingsDialogContentProps {
  activeTab: number;
  getValue: <K extends keyof SettingsUpdate>(key: K) => any;
  onSettingChange: (key: keyof SettingsUpdate, value: any) => void;
  onAddFolder: () => Promise<void>;
  onRemoveFolder: (folder: string) => void;
  onScanNow: () => void;
}

/**
 * SettingsDialogContent - Content area with tab panels
 *
 * Displays the appropriate settings panel based on active tab.
 */
export const SettingsDialogContentComponent: React.FC<SettingsDialogContentProps> = ({
  activeTab,
  getValue,
  onSettingChange,
  onAddFolder,
  onRemoveFolder,
  onScanNow,
}) => {
  return (
    <StyledContent>
      {activeTab === 0 && (
        <LibrarySettingsPanel
          scanFolders={getValue('scan_folders') ?? []}
          autoScan={getValue('auto_scan')}
          scanInterval={getValue('scan_interval')}
          onSettingChange={onSettingChange}
          onAddFolder={onAddFolder}
          onRemoveFolder={onRemoveFolder}
          onScanNow={onScanNow}
        />
      )}

      {activeTab === 1 && (
        <PlaybackSettingsPanel
          gaplessEnabled={getValue('gapless_enabled')}
          crossfadeEnabled={getValue('crossfade_enabled')}
          crossfadeDuration={getValue('crossfade_duration')}
          replayGainEnabled={getValue('replay_gain_enabled')}
          volume={getValue('volume')}
          onSettingChange={onSettingChange}
        />
      )}

      {activeTab === 2 && (
        <AudioSettingsPanel
          outputDevice={getValue('output_device')}
          bitDepth={getValue('bit_depth')}
          sampleRate={getValue('sample_rate')}
          onSettingChange={onSettingChange}
        />
      )}

      {activeTab === 3 && (
        <InterfaceSettingsPanel
          theme={getValue('theme')}
          showVisualizations={getValue('show_visualizations')}
          miniPlayerOnClose={getValue('mini_player_on_close')}
          onSettingChange={onSettingChange}
        />
      )}

      {activeTab === 4 && (
        <EnhancementSettingsPanel
          defaultPreset={getValue('default_preset')}
          autoEnhance={getValue('auto_enhance')}
          enhancementIntensity={getValue('enhancement_intensity')}
          onSettingChange={onSettingChange}
        />
      )}

      {activeTab === 5 && (
        <AdvancedSettingsPanel
          cacheSize={getValue('cache_size')}
          maxConcurrentScans={getValue('max_concurrent_scans')}
          enableAnalytics={getValue('enable_analytics')}
          debugMode={getValue('debug_mode')}
          onSettingChange={onSettingChange}
        />
      )}
    </StyledContent>
  );
};

export default SettingsDialogContentComponent;
