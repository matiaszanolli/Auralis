/**
 * MetadataDetailFields - Detail metadata fields (genre, year, track, disc, composer)
 */

import React from 'react';
import Grid2 from '@mui/material/Unstable_Grid2';
import { StyledTextField } from '../Styles/FormFields.styles';
import type { MetadataFields } from './useMetadataForm';

interface MetadataDetailFieldsProps {
  metadata: MetadataFields;
  onChange: (field: keyof MetadataFields, value: string) => void;
}

export const MetadataDetailFields = ({
  metadata,
  onChange,
}: MetadataDetailFieldsProps) => {
  return (
    <>
      {/* Genre & Year */}
      <Grid2 xs={12} sm={6}>
        <StyledTextField
          fullWidth
          label="Genre"
          value={metadata.genre || ''}
          onChange={(e) => onChange('genre', e.target.value)}
          variant="outlined"
        />
      </Grid2>

      <Grid2 xs={12} sm={6}>
        <StyledTextField
          fullWidth
          label="Year"
          type="number"
          value={metadata.year || ''}
          onChange={(e) => onChange('year', e.target.value)}
          variant="outlined"
        />
      </Grid2>

      {/* Track & Disc Numbers */}
      <Grid2 xs={6} sm={3}>
        <StyledTextField
          fullWidth
          label="Track #"
          type="number"
          value={metadata.track || ''}
          onChange={(e) => onChange('track', e.target.value)}
          variant="outlined"
        />
      </Grid2>

      <Grid2 xs={6} sm={3}>
        <StyledTextField
          fullWidth
          label="Disc #"
          type="number"
          value={metadata.disc || ''}
          onChange={(e) => onChange('disc', e.target.value)}
          variant="outlined"
        />
      </Grid2>

      {/* Composer */}
      <Grid2 xs={12} sm={6}>
        <StyledTextField
          fullWidth
          label="Composer"
          value={metadata.composer || ''}
          onChange={(e) => onChange('composer', e.target.value)}
          variant="outlined"
        />
      </Grid2>
    </>
  );
};

export default MetadataDetailFields;
