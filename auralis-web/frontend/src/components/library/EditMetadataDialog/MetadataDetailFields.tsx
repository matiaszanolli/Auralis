/**
 * MetadataDetailFields - Detail metadata fields (genre, year, track, disc, composer)
 */

import React from 'react';
import { Grid } from '@mui/material';
import { StyledTextField } from '../Styles/FormFields.styles';
import type { MetadataFields } from './useMetadataForm';

interface MetadataDetailFieldsProps {
  metadata: MetadataFields;
  onChange: (field: keyof MetadataFields, value: string) => void;
}

export const MetadataDetailFields: React.FC<MetadataDetailFieldsProps> = ({
  metadata,
  onChange,
}) => {
  return (
    <>
      {/* Genre & Year */}
      <Grid item xs={12} sm={6}>
        <StyledTextField
          fullWidth
          label="Genre"
          value={metadata.genre || ''}
          onChange={(e) => onChange('genre', e.target.value)}
          variant="outlined"
        />
      </Grid>

      <Grid item xs={12} sm={6}>
        <StyledTextField
          fullWidth
          label="Year"
          type="number"
          value={metadata.year || ''}
          onChange={(e) => onChange('year', e.target.value)}
          variant="outlined"
        />
      </Grid>

      {/* Track & Disc Numbers */}
      <Grid item xs={6} sm={3}>
        <StyledTextField
          fullWidth
          label="Track #"
          type="number"
          value={metadata.track || ''}
          onChange={(e) => onChange('track', e.target.value)}
          variant="outlined"
        />
      </Grid>

      <Grid item xs={6} sm={3}>
        <StyledTextField
          fullWidth
          label="Disc #"
          type="number"
          value={metadata.disc || ''}
          onChange={(e) => onChange('disc', e.target.value)}
          variant="outlined"
        />
      </Grid>

      {/* Composer */}
      <Grid item xs={12} sm={6}>
        <StyledTextField
          fullWidth
          label="Composer"
          value={metadata.composer || ''}
          onChange={(e) => onChange('composer', e.target.value)}
          variant="outlined"
        />
      </Grid>
    </>
  );
};

export default MetadataDetailFields;
