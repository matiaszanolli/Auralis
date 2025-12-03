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
import { Grid, Box } from '@mui/material';
import { CircularProgress } from '@/design-system';
import MetadataBasicFields from './MetadataBasicFields';
import MetadataDetailFields from './MetadataDetailFields';
import MetadataExtendedFields from './MetadataExtendedFields';
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
      <MetadataBasicFields metadata={metadata} onChange={onChange} />
      <MetadataDetailFields metadata={metadata} onChange={onChange} />
      <MetadataExtendedFields metadata={metadata} onChange={onChange} />
    </Grid>
  );
};

export default MetadataFormFields;
