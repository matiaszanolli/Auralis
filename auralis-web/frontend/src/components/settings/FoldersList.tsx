/**
 * FoldersList - Library folders list with add and remove buttons
 */

import FolderIcon from '@mui/icons-material/Folder';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import { SectionContainer, SectionLabel, SectionDescription } from '@/components/library/Styles/Dialog.styles';
import { Button } from '@/design-system/primitives/Button';
import { IconButton } from '@/design-system/primitives/IconButton';
import { List } from '@/design-system/primitives/List';
import { tokens } from '@/design-system/tokens';
import { themeVars } from '@/theme/semanticTheme';
import { Box, ListItem, ListItemText, ListItemSecondaryAction, Typography } from '@mui/material';

interface FoldersListProps {
  scanFolders: string[];
  onAddFolder: () => Promise<void>;
  onRemoveFolder: (folder: string) => void;
}

export const FoldersList = ({
  scanFolders,
  onAddFolder,
  onRemoveFolder,
}: FoldersListProps) => {
  return (
    <SectionContainer>
      <SectionLabel>Scan Folders</SectionLabel>
      <SectionDescription>
        Folders to scan for music files. The auto-scanner monitors these directories continuously.
      </SectionDescription>
      <List>
        {scanFolders.length === 0 && (
          <ListItem sx={{ px: 0, py: 2, flexDirection: 'column', alignItems: 'center', gap: 1 }}>
            <FolderOpenIcon sx={{ fontSize: 36, color: themeVars.textDisabled }} />
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2" sx={{ color: themeVars.textSecondary, fontWeight: tokens.typography.fontWeight.medium }}>
                No music folders added
              </Typography>
              <Typography variant="caption" sx={{ color: themeVars.textMuted }}>
                Add a folder below to start building your library
              </Typography>
            </Box>
          </ListItem>
        )}
        {scanFolders.map((folder: string) => {
          const basename = folder.split('/').filter(Boolean).pop() ?? folder;
          return (
            <ListItem key={folder} sx={{ px: 0, py: 1 }}>
              <FolderIcon sx={{ mr: 2, flexShrink: 0, color: themeVars.accent }} />
              <ListItemText
                primary={basename}
                secondary={folder}
                slotProps={{
                  // #4465: were 0.9rem/0.75rem — off the token scale entirely.
                  // base (14px) is the standard body size; sm (13px) is the
                  // scale's designated metadata/caption size, and is no further
                  // from the old 12px than xs (11px), which is the WCAG AA floor.
                  primary: { sx: { fontSize: tokens.typography.fontSize.base, fontWeight: tokens.typography.fontWeight.medium } },
                  secondary: {
                    noWrap: true,
                    title: folder,
                    sx: { fontSize: tokens.typography.fontSize.sm, color: themeVars.textMuted },
                  },
                }}
              />
              <ListItemSecondaryAction>
                <IconButton
                  onClick={() => onRemoveFolder(folder)}
                  size="sm"
                  tooltip="Remove this folder"
                  sx={{ color: themeVars.error }}
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
          borderColor: themeVars.accent,
          color: themeVars.accent,
          '&:hover': {
            borderColor: themeVars.accentHover,
            backgroundColor: themeVars.accentSoft,
          },
        }}
      >
        Add Folder
      </Button>
    </SectionContainer>
  );
};

export default FoldersList;
