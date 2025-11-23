/**
 * MetadataBasicFields - Basic metadata fields (title, artist, album)
 */

import React from 'react';
import { Grid } from '@mui/material';
import { StyledTextField } from '../Styles/FormFields.styles';
import type { MetadataFields } from './useMetadataForm';

interface MetadataBasicFieldsProps {
  metadata: MetadataFields;
  onChange: (field: keyof MetadataFields, value: string) => void;
}

export const MetadataBasicFields: React.FC<MetadataBasicFieldsProps> = ({
  metadata,
  onChange,
}) => {
  return (
    <>
      {/* Title */}
      <Grid item xs={12}>
        <StyledTextField
          fullWidth
          label="Title"
          value={metadata.title || ''}
          onChange={(e) => onChange('title', e.target.value)}
          variant="outlined"
        />
      </Grid>

      {/* Artist & Album Artist */}
      <Grid item xs={12} sm={6}>
        <StyledTextField
          fullWidth
          label="Artist"
          value={metadata.artist || ''}
          onChange={(e) => onChange('artist', e.target.value)}
          variant="outlined"
        />
      </Grid>

      <Grid item xs={12} sm={6}>
        <StyledTextField
          fullWidth
          label="Album Artist"
          value={metadata.albumartist || ''}
          onChange={(e) => onChange('albumartist', e.target.value)}
          variant="outlined"
        />
      </Grid>

      {/* Album */}
      <Grid item xs={12}>
        <StyledTextField
          fullWidth
          label="Album"
          value={metadata.album || ''}
          onChange={(e) => onChange('album', e.target.value)}
          variant="outlined"
        />
      </Grid>
    </>
  );
};

export default MetadataBasicFields;
