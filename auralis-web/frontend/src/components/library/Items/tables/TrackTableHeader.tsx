/**
 * TrackTableHeader - Album track table header
 */

import React from 'react';
import { TableHead, TableRow, TableCell } from '@mui/material';
import { tokens } from '@/design-system';

export const TrackTableHeader: React.FC = () => {
  return (
    <TableHead>
      <TableRow sx={{
        backgroundColor: `rgba(${parseInt(tokens.colors.bg.level3.slice(1, 3), 16)}, ${parseInt(tokens.colors.bg.level3.slice(3, 5), 16)}, ${parseInt(tokens.colors.bg.level3.slice(5, 7), 16)}, 0.5)`,
        borderBottom: `1px solid ${tokens.colors.border.light}`,
      }}>
        <TableCell width="60px" sx={{
          color: tokens.colors.text.tertiary,
          fontWeight: tokens.typography.fontWeight.semibold,
          fontSize: tokens.typography.fontSize.xs,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          padding: `${tokens.spacing.md} ${tokens.spacing.sm}`,
        }}>
          #
        </TableCell>
        <TableCell sx={{
          color: tokens.colors.text.tertiary,
          fontWeight: tokens.typography.fontWeight.semibold,
          fontSize: tokens.typography.fontSize.xs,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          padding: `${tokens.spacing.md} ${tokens.spacing.sm}`,
        }}>
          Title
        </TableCell>
        <TableCell sx={{
          color: tokens.colors.text.tertiary,
          fontWeight: tokens.typography.fontWeight.semibold,
          fontSize: tokens.typography.fontSize.xs,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          padding: `${tokens.spacing.md} ${tokens.spacing.sm}`,
        }}>
          Artist
        </TableCell>
        <TableCell align="right" width="100px" sx={{
          color: tokens.colors.text.tertiary,
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
