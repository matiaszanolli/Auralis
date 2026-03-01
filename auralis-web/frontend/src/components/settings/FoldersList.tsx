/**
 * FoldersList - Library folders list with add and remove buttons
 */

import React from 'react';

import {
  Folder as FolderIcon,
  FolderOpen as FolderOpenIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
} from '@mui/icons-material';
import { SectionContainer, SectionLabel, SectionDescription } from '../library/Styles/Dialog.styles';
import { tokens } from '@/design-system';
import { List, IconButton, Button } from '@/design-system';
import { Box, ListItem, ListItemText, ListItemSecondaryAction, Typography } from '@mui/material';

interface FoldersListProps {
  scanFolders: string[];
  onAddFolder: () => Promise<void>;
  onRemoveFolder: (folder: string) => void;
}

export const FoldersList: React.FC<FoldersListProps> = ({
  scanFolders,
  onAddFolder,
  onRemoveFolder,
}) => {
  return (
    <SectionContainer>
      <SectionLabel>Scan Folders</SectionLabel>
      <SectionDescription>
        Folders to scan for music files. The auto-scanner monitors these directories continuously.
      </SectionDescription>
      <List>
        {scanFolders.length === 0 && (
          <ListItem sx={{ px: 0, py: 2, flexDirection: 'column', alignItems: 'center', gap: 1 }}>
            <FolderOpenIcon sx={{ fontSize: 36, color: tokens.colors.text.disabled }} />
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2" sx={{ color: tokens.colors.text.secondary, fontWeight: 500 }}>
                No music folders added
              </Typography>
              <Typography variant="caption" sx={{ color: tokens.colors.text.metadata }}>
                Add a folder below to start building your library
              </Typography>
            </Box>
          </ListItem>
        )}
        {scanFolders.map((folder: string) => {
          const basename = folder.split('/').filter(Boolean).pop() ?? folder;
          return (
            <ListItem key={folder} sx={{ px: 0, py: 1 }}>
              <FolderIcon sx={{ mr: 2, flexShrink: 0, color: tokens.colors.accent.primary }} />
              <ListItemText
                primary={basename}
                secondary={folder}
                primaryTypographyProps={{ fontSize: '0.9rem', fontWeight: 500 }}
                secondaryTypographyProps={{
                  fontSize: '0.75rem',
                  color: tokens.colors.text.metadata,
                  noWrap: true,
                  title: folder,
                }}
              />
              <ListItemSecondaryAction>
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
          );
        })}
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
            backgroundColor: tokens.colors.opacityScale.accent.standard,
          },
        }}
      >
        Add Folder
      </Button>
    </SectionContainer>
  );
};

export default FoldersList;
