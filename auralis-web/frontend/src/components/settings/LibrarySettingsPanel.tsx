import React from 'react';
import { Box } from '@mui/material';
import FoldersList from './FoldersList';
import AutoScanSettings from './AutoScanSettings';

interface LibrarySettingsPanelProps {
  scanFolders: string[];
  autoScan: boolean;
  scanInterval: number;
  onSettingChange: (key: string, value: any) => void;
  onAddFolder: () => Promise<void>;
  onRemoveFolder: (folder: string) => Promise<void>;
  onRescanFolder: (folder: string) => Promise<void>;
}

/**
 * LibrarySettingsPanel - Library folder and auto-scan settings
 *
 * Manages:
 * - Scan folders list (add, remove, rescan)
 * - Auto-scan toggle
 * - Scan interval configuration
 */
export const LibrarySettingsPanel: React.FC<LibrarySettingsPanelProps> = ({
  scanFolders,
  autoScan,
  scanInterval,
  onSettingChange,
  onAddFolder,
  onRemoveFolder,
  onRescanFolder,
}) => {
  return (
    <Box>
      <FoldersList
        scanFolders={scanFolders}
        onAddFolder={onAddFolder}
        onRemoveFolder={onRemoveFolder}
        onRescanFolder={onRescanFolder}
      />
      <AutoScanSettings
        autoScan={autoScan}
        scanInterval={scanInterval}
        onSettingChange={onSettingChange}
      />
    </Box>
  );
};

export default LibrarySettingsPanel;
