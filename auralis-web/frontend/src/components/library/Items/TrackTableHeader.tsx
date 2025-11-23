/**
 * TrackTableHeader - Album track table header
 */

import React from 'react';
import { TableHead, TableRow, TableCell } from '@mui/material';

export const TrackTableHeader: React.FC = () => {
  return (
    <TableHead>
      <TableRow>
        <TableCell width="60px" sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
          #
        </TableCell>
        <TableCell sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
          Title
        </TableCell>
        <TableCell sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
          Artist
        </TableCell>
        <TableCell align="right" width="100px" sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
          Duration
        </TableCell>
      </TableRow>
    </TableHead>
  );
};

export default TrackTableHeader;
