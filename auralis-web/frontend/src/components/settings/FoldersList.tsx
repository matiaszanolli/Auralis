/**
 * FoldersList - Library folders list with add, remove, and rescan buttons
 */

import React from 'react';

import {
  Folder as FolderIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { SectionContainer, SectionLabel, SectionDescription } from '../library/Styles/Dialog.styles';
import { auroraOpacity } from '../library/Styles/Color.styles';
import { tokens } from '@/design-system';
import { List, IconButton, Button } from '@/design-system';
import { Box, ListItem, ListItemText, ListItemSecondaryAction,  } from '@mui/material';

interface FoldersListProps {
  scanFolders: string[];
  onAddFolder: () => Promise<void>;
  onRemoveFolder: (folder: string) => Promise<void>;
  onRescanFolder: (folder: string) => Promise<void>;
}

export const FoldersList: React.FC<FoldersListProps> = ({
  scanFolders,
  onAddFolder,
  onRemoveFolder,
  onRescanFolder,
}) => {
  return (
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
            <FolderIcon sx={{ mr: 2, color: tokens.colors.accent.primary }} />
            <ListItemText
              primary={folder}
              primaryTypographyProps={{ fontSize: '0.9rem' }}
            />
            <ListItemSecondaryAction>
              <IconButton
                onClick={() => onRescanFolder(folder)}
                size="sm"
                sx={{ mr: 1 }}
                tooltip="Rescan this folder"
              >
                <RefreshIcon fontSize="small" />
              </IconButton>
              <IconButton
                onClick={() => onRemoveFolder(folder)}
                size="sm"
                tooltip="Remove this folder"
                sx={{ color: tokens.colors.semantic.error }}
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
        variant="secondary"
        sx={{
          borderColor: tokens.colors.accent.primary,
          color: tokens.colors.accent.primary,
          '&:hover': {
            borderColor: tokens.colors.accent.primary,
            backgroundColor: auroraOpacity.standard,
          },
        }}
      >
        Add Folder
      </Button>
    </SectionContainer>
  );
};

export default FoldersList;
