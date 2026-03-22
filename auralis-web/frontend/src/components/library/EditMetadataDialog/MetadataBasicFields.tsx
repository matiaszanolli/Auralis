/**
 * MetadataBasicFields - Basic metadata fields (title, artist, album)
 */

import React from 'react';
import Grid2 from '@mui/material/Unstable_Grid2';
import { StyledTextField } from '@/components/library/Styles/FormFields.styles';
import type { MetadataFields } from './useMetadataForm';

interface MetadataBasicFieldsProps {
  metadata: MetadataFields;
  onChange: (field: keyof MetadataFields, value: string) => void;
}

export const MetadataBasicFields = ({
  metadata,
  onChange,
}: MetadataBasicFieldsProps) => {
  return (
    <>
      {/* Title */}
      <Grid2 xs={12}>
        <StyledTextField
          fullWidth
          label="Title"
          value={metadata.title || ''}
          onChange={(e) => onChange('title', e.target.value)}
          variant="outlined"
        />
      </Grid2>

      {/* Artist & Album Artist */}
      <Grid2 xs={12} sm={6}>
        <StyledTextField
          fullWidth
          label="Artist"
          value={metadata.artist || ''}
          onChange={(e) => onChange('artist', e.target.value)}
          variant="outlined"
        />
      </Grid2>

      <Grid2 xs={12} sm={6}>
        <StyledTextField
          fullWidth
          label="Album Artist"
          value={metadata.albumartist || ''}
          onChange={(e) => onChange('albumartist', e.target.value)}
          variant="outlined"
        />
      </Grid2>

      {/* Album */}
      <Grid2 xs={12}>
        <StyledTextField
          fullWidth
          label="Album"
          value={metadata.album || ''}
          onChange={(e) => onChange('album', e.target.value)}
          variant="outlined"
        />
      </Grid2>
    </>
  );
};

export default MetadataBasicFields;
