/**
 * ArtworkMenu Component
 *
 * Dropdown menu for artwork management options:
 * - Download artwork
 * - Extract from files
 * - Delete existing artwork
 */

import { Menu, MenuItem } from '@mui/material';
import CloudDownload from '@mui/icons-material/CloudDownload';
import ImageSearch from '@mui/icons-material/ImageSearch';
import Delete from '@mui/icons-material/Delete';

export interface ArtworkMenuProps {
  open: boolean;
  anchorEl: HTMLElement | null;
  onClose: () => void;
  hasArtwork: boolean;
  onDownload: () => void;
  onExtract: () => void;
  onDelete: () => void;
  isDownloading?: boolean;
  isExtracting?: boolean;
}

export const ArtworkMenu = ({
  open,
  anchorEl,
  onClose,
  hasArtwork,
  onDownload,
  onExtract,
  onDelete,
  isDownloading = false,
  isExtracting = false,
}: ArtworkMenuProps) => {
  return (
    <Menu
      anchorEl={anchorEl}
      open={open}
      onClose={onClose}
      onClick={(e) => e.stopPropagation()}
    >
      <MenuItem onClick={onDownload} disabled={isDownloading}>
        <CloudDownload sx={{ mr: 1 }} fontSize="small" />
        Download Artwork
      </MenuItem>
      <MenuItem onClick={onExtract} disabled={isExtracting}>
        <ImageSearch sx={{ mr: 1 }} fontSize="small" />
        Extract from Files
      </MenuItem>
      {hasArtwork && (
        <MenuItem onClick={onDelete}>
          <Delete sx={{ mr: 1 }} fontSize="small" />
          Delete Artwork
        </MenuItem>
      )}
    </Menu>
  );
};

export default ArtworkMenu;
