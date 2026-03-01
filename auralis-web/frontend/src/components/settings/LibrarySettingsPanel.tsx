import React from 'react';
import { Box } from '@mui/material';
import { SettingsUpdate } from '../../services/settingsService';
import FoldersList from './FoldersList';
import AutoScanSettings from './AutoScanSettings';
import ScanStatusCard from './ScanStatusCard';
import { tokens } from '@/design-system';

interface LibrarySettingsPanelProps {
  scanFolders: string[];
  autoScan: boolean;
  scanInterval: number;
  onSettingChange: (key: keyof SettingsUpdate, value: any) => void;
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
 * - Auto-scan toggle and interval
 */
export const LibrarySettingsPanel: React.FC<LibrarySettingsPanelProps> = ({
  scanFolders,
  autoScan,
  scanInterval,
  onSettingChange,
  onAddFolder,
  onRemoveFolder,
  onScanNow,
}) => {
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
      <AutoScanSettings
        autoScan={autoScan}
        scanInterval={scanInterval}
        onSettingChange={onSettingChange}
      />
    </Box>
  );
};

export default LibrarySettingsPanel;
