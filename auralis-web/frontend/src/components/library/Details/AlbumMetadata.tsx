/**
 * AlbumMetadata - Display album metadata (year, track count, duration, genre)
 *
 * Shows secondary information about album beneath title.
 */

import { Box, Typography } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';
import { formatHoursMinutes } from '@/utils/timeFormat';

interface AlbumMetadataProps {
  year?: number;
  trackCount: number;
  totalDuration: number;
  genre?: string;
}

export const AlbumMetadata = ({
  year,
  trackCount,
  totalDuration,
  genre,
}: AlbumMetadataProps) => {
  return (
    <Box>
      <Typography variant="body2" sx={{
        color: themeVars.textMuted,
        mb: tokens.spacing.sm,
        fontSize: tokens.typography.fontSize.sm,
        fontWeight: tokens.typography.fontWeight.normal,
      }}>
        {year && `${year} • `}
        {trackCount} {trackCount === 1 ? 'track' : 'tracks'}
        {' • '}
        {formatHoursMinutes(totalDuration, 'long')}
      </Typography>
      {genre && (
        <Typography variant="body2" sx={{
          color: themeVars.textMuted,
          fontSize: tokens.typography.fontSize.sm,
          fontWeight: tokens.typography.fontWeight.normal,
        }}>
          Genre: {genre}
        </Typography>
      )}
    </Box>
  );
};
