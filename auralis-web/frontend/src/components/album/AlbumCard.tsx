/**
 * AlbumCard Component
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Album card with artwork, title, artist, and artwork management options.
 * Includes buttons to download/extract artwork when missing.
 */

import React, { useState } from 'react';
import {
  Box,
  Card,
  CardMedia,
  CardContent,
  Typography,
  IconButton,
  Menu,
  MenuItem,
  CircularProgress,
  Tooltip,
} from '@mui/material';
import {
  MoreVert,
  CloudDownload,
  ImageSearch,
  Delete,
  Album as AlbumIcon,
} from '@mui/icons-material';
import { AlbumArt } from './AlbumArt';
import { downloadArtwork, extractArtwork, deleteArtwork } from '../../services/artworkService';
import { useToast } from '../shared/Toast';
import { colors, gradients } from '../../theme/auralisTheme';

interface AlbumCardProps {
  albumId: number;
  title: string;
  artist: string;
  hasArtwork?: boolean;
  trackCount?: number;
  onClick?: () => void;
  onArtworkUpdated?: () => void;
}

export const AlbumCard: React.FC<AlbumCardProps> = ({
  albumId,
  title,
  artist,
  hasArtwork = false,
  trackCount = 0,
  onClick,
  onArtworkUpdated,
}) => {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [downloading, setDownloading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const { success, error: showError } = useToast();

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleDownloadArtwork = async () => {
    handleMenuClose();
    setDownloading(true);

    try {
      const result = await downloadArtwork(albumId);
      success(`Downloaded artwork for "${result.album}" by ${result.artist}`);
      onArtworkUpdated?.();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to download artwork');
    } finally {
      setDownloading(false);
    }
  };

  const handleExtractArtwork = async () => {
    handleMenuClose();
    setExtracting(true);

    try {
      const result = await extractArtwork(albumId);
      success(`Extracted artwork from audio files`);
      onArtworkUpdated?.();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to extract artwork');
    } finally {
      setExtracting(false);
    }
  };

  const handleDeleteArtwork = async () => {
    handleMenuClose();

    try {
      await deleteArtwork(albumId);
      success('Artwork deleted');
      onArtworkUpdated?.();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to delete artwork');
    }
  };

  return (
    <Card
      sx={{
        position: 'relative',
        borderRadius: 2,
        overflow: 'hidden',
        cursor: 'pointer',
        transition: 'all 0.3s ease',
        background: colors.background.surface,
        border: `1px solid ${colors.background.hover}`,
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: `0 8px 24px rgba(102, 126, 234, 0.2)`,
          border: `1px solid rgba(102, 126, 234, 0.3)`,
        },
      }}
      onClick={onClick}
    >
      {/* Artwork */}
      <Box sx={{ position: 'relative' }}>
        <AlbumArt albumId={albumId} size="100%" borderRadius={0} />

        {/* Loading overlay */}
        {(downloading || extracting) && (
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(0, 0, 0, 0.7)',
              backdropFilter: 'blur(4px)',
            }}
          >
            <CircularProgress size={40} sx={{ color: '#667eea' }} />
          </Box>
        )}

        {/* No artwork overlay */}
        {!hasArtwork && !downloading && !extracting && (
          <Box
            sx={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              p: 1,
              background: 'linear-gradient(to top, rgba(0,0,0,0.8), transparent)',
              display: 'flex',
              gap: 0.5,
              justifyContent: 'center',
            }}
          >
            <Tooltip title="Download from online sources">
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDownloadArtwork();
                }}
                sx={{
                  color: '#fff',
                  background: gradients.aurora,
                  '&:hover': { background: gradients.electricPurple },
                }}
              >
                <CloudDownload fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Extract from audio files">
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  handleExtractArtwork();
                }}
                sx={{
                  color: '#fff',
                  background: 'rgba(255, 255, 255, 0.2)',
                  '&:hover': { background: 'rgba(255, 255, 255, 0.3)' },
                }}
              >
                <ImageSearch fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        )}

        {/* Options menu button */}
        <IconButton
          onClick={handleMenuOpen}
          sx={{
            position: 'absolute',
            top: 8,
            right: 8,
            color: '#fff',
            background: 'rgba(0, 0, 0, 0.5)',
            backdropFilter: 'blur(10px)',
            '&:hover': { background: 'rgba(0, 0, 0, 0.7)' },
          }}
        >
          <MoreVert />
        </IconButton>

        {/* Options menu */}
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleMenuClose}
          onClick={(e) => e.stopPropagation()}
        >
          <MenuItem onClick={handleDownloadArtwork} disabled={downloading}>
            <CloudDownload sx={{ mr: 1 }} fontSize="small" />
            Download Artwork
          </MenuItem>
          <MenuItem onClick={handleExtractArtwork} disabled={extracting}>
            <ImageSearch sx={{ mr: 1 }} fontSize="small" />
            Extract from Files
          </MenuItem>
          {hasArtwork && (
            <MenuItem onClick={handleDeleteArtwork}>
              <Delete sx={{ mr: 1 }} fontSize="small" />
              Delete Artwork
            </MenuItem>
          )}
        </Menu>
      </Box>

      {/* Album info */}
      <CardContent sx={{ p: 2 }}>
        <Typography
          variant="subtitle1"
          sx={{
            fontWeight: 600,
            color: colors.text.primary,
            mb: 0.5,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {title}
        </Typography>
        <Typography
          variant="body2"
          sx={{
            color: colors.text.secondary,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {artist}
        </Typography>
        {trackCount > 0 && (
          <Typography
            variant="caption"
            sx={{
              color: colors.text.disabled,
              mt: 0.5,
              display: 'block',
            }}
          >
            {trackCount} {trackCount === 1 ? 'track' : 'tracks'}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};
