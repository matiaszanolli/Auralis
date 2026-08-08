/**
 * TrackTableHeader - Album track table header
 */

import { TableHead, TableRow, TableCell } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

export const TrackTableHeader = () => {
  return (
    <TableHead>
      <TableRow sx={{
        // #4877: was a manual rgba() built by slicing tokens.colors.bg.level3's
        // hex digits — a dark-only computation that broke under light mode.
        // color-mix() applies the same 50% alpha to whichever theme-aware
        // surface is active (matches the pattern in AppMainContent.tsx /
        // AppContainer.tsx).
        backgroundColor: `color-mix(in srgb, ${themeVars.surfaceRaised} 50%, transparent)`,
        borderBottom: `1px solid ${tokens.colors.border.light}`,
      }}>
        <TableCell width="60px" sx={{
          color: themeVars.textMuted,
          fontWeight: tokens.typography.fontWeight.semibold,
          fontSize: tokens.typography.fontSize.xs,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          padding: `${tokens.spacing.md} ${tokens.spacing.sm}`,
        }}>
          #
        </TableCell>
        <TableCell sx={{
          color: themeVars.textMuted,
          fontWeight: tokens.typography.fontWeight.semibold,
          fontSize: tokens.typography.fontSize.xs,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          padding: `${tokens.spacing.md} ${tokens.spacing.sm}`,
        }}>
          Title
        </TableCell>
        <TableCell sx={{
          color: themeVars.textMuted,
          fontWeight: tokens.typography.fontWeight.semibold,
          fontSize: tokens.typography.fontSize.xs,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          padding: `${tokens.spacing.md} ${tokens.spacing.sm}`,
        }}>
          Artist
        </TableCell>
        <TableCell align="right" width="100px" sx={{
          color: themeVars.textMuted,
          fontWeight: tokens.typography.fontWeight.semibold,
          fontSize: tokens.typography.fontSize.xs,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          padding: `${tokens.spacing.md} ${tokens.spacing.sm}`,
        }}>
          Duration
        </TableCell>
      </TableRow>
    </TableHead>
  );
};

export default TrackTableHeader;
