import React from 'react';
import {
  ListItem,
  ListItemButton,
  ListItemText,
  Box,
  Typography,
  Divider
} from '@mui/material';
import { Tooltip, Chip, tokens } from '@/design-system';
import { SimilarTrack } from '@/services/similarityService';

interface SimilarTracksListItemProps {
  track: SimilarTrack;
  index: number;
  totalCount: number;
  onClick: (track: SimilarTrack) => void;
  getSimilarityColor: (score: number) => string;
  formatDuration: (seconds?: number) => string;
}

/**
 * SimilarTracksListItem - Individual track row with similarity score
 */
export const SimilarTracksListItem: React.FC<SimilarTracksListItemProps> = ({
  track,
  index,
  totalCount,
  onClick,
  getSimilarityColor,
  formatDuration,
}) => {
  return (
    <>
      <ListItem disablePadding>
        <ListItemButton
          onClick={() => onClick(track)}
          sx={{
            px: 2,
            py: 1.5,
            '&:hover': {
              backgroundColor: 'rgba(115, 102, 240, 0.08)'
            }
          }}
        >
          {/* Track Info */}
          <ListItemText
            primary={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography
                  variant="body2"
                  sx={{
                    color: tokens.colors.text.primary,
                    fontWeight: 500,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    flex: 1
                  }}
                >
                  {track.title}
                </Typography>
                {/* Similarity Badge */}
                <Tooltip title={`${(track.similarity_score * 100).toFixed(1)}% similar`}>
                  <Chip
                    label={`${Math.round(track.similarity_score * 100)}%`}
                    size="small"
                    sx={{
                      height: 20,
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      backgroundColor: getSimilarityColor(track.similarity_score),
                      color: tokens.colors.text.primary,
                      '& .MuiChip-label': {
                        px: 1
                      }
                    }}
                  />
                </Tooltip>
              </Box>
            }
            secondary={
              <Typography
                variant="caption"
                sx={{
                  color: tokens.colors.text.secondary,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  display: 'block'
                }}
              >
                {track.artist}
                {track.duration && ` • ${formatDuration(track.duration)}`}
              </Typography>
            }
          />
        </ListItemButton>
      </ListItem>
      {index < totalCount - 1 && (
        <Divider sx={{ borderColor: 'rgba(115, 102, 240, 0.05)' }} />
      )}
    </>
  );
};

export default SimilarTracksListItem;
