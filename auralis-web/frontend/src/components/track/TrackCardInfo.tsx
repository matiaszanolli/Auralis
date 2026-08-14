/**
 * TrackCardInfo Component
 *
 * Renders track metadata section:
 * - Track title
 * - Artist name
 * - Album name
 */

import { tokens } from '@/design-system';
import { TrackCardContent } from './TrackCardStyles';
import { Tooltip } from '@/design-system';
import { Typography } from '@mui/material';
import { themeVars } from '@/theme/semanticTheme';

interface TrackCardInfoProps {
  title: string;
  artist: string;
  album: string;
  isPlaying?: boolean;
}

export const TrackCardInfo = ({
  title,
  artist,
  album,
  isPlaying = false,
}: TrackCardInfoProps) => {
  return (
    <TrackCardContent>
      <Tooltip title={title} placement="top">
        <Typography
          variant="subtitle1"
          sx={{
            fontWeight: isPlaying ? tokens.typography.fontWeight.bold : tokens.typography.fontWeight.semibold, // Higher contrast for visual anchor
            color: themeVars.textPrimary,
            mb: 1,
            lineHeight: 1.4,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            opacity: isPlaying ? 1 : 0.95, // Slightly more prominent when playing
          }}
        >
          {title}
        </Typography>
      </Tooltip>

      <Tooltip title={artist} placement="top">
        <Typography
          variant="body2"
          sx={{
            color: themeVars.textSecondary,
            fontWeight: tokens.typography.fontWeight.normal, // Reduced from default (less weight variance)
            lineHeight: 1.5, // Increased for secondary text breathing room
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            mb: 0.75, // Increased from 0.5 for more spacing
          }}
        >
          {artist}
        </Typography>
      </Tooltip>

      <Tooltip title={album} placement="top">
        <Typography
          variant="caption"
          sx={{
            color: themeVars.textMuted, // Changed from disabled to tertiary (better hierarchy)
            fontWeight: tokens.typography.fontWeight.normal,
            lineHeight: 1.5,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            display: 'block',
          }}
        >
          {album}
        </Typography>
      </Tooltip>
    </TrackCardContent>
  );
};
