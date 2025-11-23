import React from 'react';
import {
  Box,
  Switch,
  FormControlLabel,
  TextField,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Button
} from '@mui/material';
import {
  Folder as FolderIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import { SectionContainer, SectionLabel, SectionDescription } from '../library/Dialog.styles';
import { auroraOpacity } from '../library/Color.styles';
import { tokens } from '@/design-system/tokens';

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
  onRescanFolder
}) => {
  return (
    <Box>
      <SectionContainer>
        <SectionLabel>Scan Folders</SectionLabel>
        <SectionDescription>
          Folders to scan for music files. Use the native folder picker to select directories.
        </SectionDescription>
        <List>
          {scanFolders.length === 0 && (
            <ListItem sx={{ px: 0 }}>
              <ListItemText
                primary="No folders added yet"
                secondary="Click 'Add Folder' below to start building your library"
                primaryTypographyProps={{ color: 'text.secondary' }}
              />
            </ListItem>
          )}
          {scanFolders.map((folder: string, index: number) => (
            <ListItem key={index} sx={{ px: 0, py: 1 }}>
              <FolderIcon sx={{ mr: 2, color: tokens.colors.accent.purple }} />
              <ListItemText
                primary={folder}
                primaryTypographyProps={{ fontSize: '0.9rem' }}
              />
              <ListItemSecondaryAction>
                <IconButton
                  onClick={() => onRescanFolder(folder)}
                  size="small"
                  sx={{ mr: 1 }}
                  title="Rescan this folder"
                >
                  <RefreshIcon fontSize="small" />
                </IconButton>
                <IconButton
                  onClick={() => onRemoveFolder(folder)}
                  size="small"
                  color="error"
                  title="Remove this folder"
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </ListItemSecondaryAction>
            </ListItem>
          ))}
        </List>
        <Button
          startIcon={<AddIcon />}
          onClick={onAddFolder}
          variant="outlined"
          sx={{
            borderColor: tokens.colors.accent.purple,
            color: tokens.colors.accent.purple,
            '&:hover': {
              borderColor: tokens.colors.accent.purple,
              backgroundColor: auroraOpacity.standard
            }
          }}
        >
          Add Folder
        </Button>
      </SectionContainer>

      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <FormControlLabel
          control={
            <Switch
              checked={autoScan}
              onChange={(e) => onSettingChange('auto_scan', e.target.checked)}
            />
          }
          label="Auto-scan library"
        />
        <SectionDescription>
          Automatically scan for new files at regular intervals
        </SectionDescription>
      </SectionContainer>

      {autoScan && (
        <SectionContainer>
          <SectionLabel>Scan Interval (seconds)</SectionLabel>
          <TextField
            type="number"
            fullWidth
            value={scanInterval}
            onChange={(e) => onSettingChange('scan_interval', parseInt(e.target.value))}
            inputProps={{ min: 60, max: 86400 }}
          />
        </SectionContainer>
      )}
    </Box>
  );
};

export default LibrarySettingsPanel;
