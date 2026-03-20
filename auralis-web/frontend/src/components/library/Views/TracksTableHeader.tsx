/**
 * TracksTableHeader - Tracks table header for artist detail view
 */

import React from 'react';
import { TableHead, TableRow, TableCell } from '@mui/material';
import { tokens } from '@/design-system';

export const TracksTableHeader = () => {
  return (
    <TableHead>
      <TableRow>
        <TableCell width="60px" sx={{ color: 'text.secondary', fontWeight: tokens.typography.fontWeight.bold }}>
          #
        </TableCell>
        <TableCell sx={{ color: 'text.secondary', fontWeight: tokens.typography.fontWeight.bold }}>
          Title
        </TableCell>
        <TableCell sx={{ color: 'text.secondary', fontWeight: tokens.typography.fontWeight.bold }}>
          Album
        </TableCell>
        <TableCell align="right" width="100px" sx={{ color: 'text.secondary', fontWeight: tokens.typography.fontWeight.bold }}>
          Duration
        </TableCell>
      </TableRow>
    </TableHead>
  );
};

export default TracksTableHeader;
