/**
 * MetadataExtendedFields - Extended metadata fields (comment)
 */

import React from 'react';
import { Grid } from '@mui/material';
import { StyledTextField } from '../Styles/FormFields.styles';
import type { MetadataFields } from './useMetadataForm';

interface MetadataExtendedFieldsProps {
  metadata: MetadataFields;
  onChange: (field: keyof MetadataFields, value: string) => void;
}

export const MetadataExtendedFields: React.FC<MetadataExtendedFieldsProps> = ({
  metadata,
  onChange,
}) => {
  return (
    <>
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
    </>
  );
};

export default MetadataExtendedFields;
