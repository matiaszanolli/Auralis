/**
 * MetadataFormFields Component
 *
 * Renders all metadata form fields in organized layout
 * Organized into logical groups:
 * - Basic info (title, artist, album)
 * - Details (genre, year, track, disc)
 * - Extended (composer, comment)
 */

import React from 'react';
import { Grid, CircularProgress, Box } from '@mui/material';
import { StyledTextField } from '../Styles/FormFields.styles';
import type { MetadataFields } from './useMetadataForm';

export interface MetadataFormFieldsProps {
  metadata: MetadataFields;
  loading: boolean;
  onChange: (field: keyof MetadataFields, value: string) => void;
}

export const MetadataFormFields: React.FC<MetadataFormFieldsProps> = ({
  metadata,
  loading,
  onChange,
}) => {
  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Grid container spacing={2}>
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

      {/* Comment */}
      <Grid item xs={12}>
        <StyledTextField
          fullWidth
          label="Comment"
          value={metadata.comment || ''}
          onChange={(e) => onChange('comment', e.target.value)}
          multiline
          rows={3}
          variant="outlined"
        />
      </Grid>
    </Grid>
  );
};

export default MetadataFormFields;
