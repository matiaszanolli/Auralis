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
import { Box } from '@mui/material';
import Grid2 from '@mui/material/Unstable_Grid2';
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

export const MetadataFormFields = ({
  metadata,
  loading,
  onChange,
}: MetadataFormFieldsProps) => {
  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Grid2 container spacing={2}>
      <MetadataBasicFields metadata={metadata} onChange={onChange} />
      <MetadataDetailFields metadata={metadata} onChange={onChange} />
      <MetadataExtendedFields metadata={metadata} onChange={onChange} />
    </Grid2>
  );
};

export default MetadataFormFields;
