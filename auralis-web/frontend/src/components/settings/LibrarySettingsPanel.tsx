
import { Box } from '@mui/material';
import { SettingsUpdate } from '@/services/settingsService';
import FoldersList from './FoldersList';
import AutoScanSettings from './AutoScanSettings';
import ScanStatusCard from './ScanStatusCard';
import FingerprintCoverageCard from './FingerprintCoverageCard';
import { tokens } from '@/design-system';

interface LibrarySettingsPanelProps {
  scanFolders: string[];
  autoScan: boolean;
  scanInterval: number;
  onSettingChange: (key: keyof SettingsUpdate, value: SettingsUpdate[keyof SettingsUpdate]) => void;
  onAddFolder: () => Promise<void>;
  onRemoveFolder: (folder: string) => void;
  onScanNow: () => void;
}

/**
 * LibrarySettingsPanel - Library folder and auto-scan settings
 *
 * Manages:
 * - Scan folders list (add, remove)
 * - Live scan status card
 * - Library-wide audio-analysis (fingerprint) coverage (#4865)
 * - Auto-scan toggle and interval
 */
export const LibrarySettingsPanel = ({
  scanFolders,
  autoScan,
  scanInterval,
  onSettingChange,
  onAddFolder,
  onRemoveFolder,
  onScanNow,
}: LibrarySettingsPanelProps) => {
  return (
    <Box>
      <FoldersList
        scanFolders={scanFolders}
        onAddFolder={onAddFolder}
        onRemoveFolder={onRemoveFolder}
      />
      <Box sx={{ mb: tokens.spacing.lg }}>
        <ScanStatusCard
          disabled={scanFolders.length === 0}
          onScanNow={onScanNow}
        />
      </Box>
      {/* Scanning finds files; analysis fingerprints them. Separate cards
          because they run on very different clocks (#4865). */}
      <Box sx={{ mb: tokens.spacing.lg }}>
        <FingerprintCoverageCard />
      </Box>
      <AutoScanSettings
        autoScan={autoScan}
        scanInterval={scanInterval}
        onSettingChange={onSettingChange}
      />
    </Box>
  );
};

export default LibrarySettingsPanel;
