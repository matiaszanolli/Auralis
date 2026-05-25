/**
 * MetadataExtendedFields - Extended metadata fields (comment)
 */

import Grid2 from '@mui/material/Grid';
import { StyledTextField } from '@/components/library/Styles/FormFields.styles';
import type { MetadataFields } from './useMetadataForm';

interface MetadataExtendedFieldsProps {
  metadata: MetadataFields;
  onChange: (field: keyof MetadataFields, value: string) => void;
}

export const MetadataExtendedFields = ({
  metadata,
  onChange,
}: MetadataExtendedFieldsProps) => {
  return (
    <>
      {/* Comment */}
      <Grid2 size={12}>
        <StyledTextField
          fullWidth
          label="Comment"
          value={metadata.comment || ''}
          onChange={(e) => onChange('comment', e.target.value)}
          multiline
          rows={3}
          variant="outlined"
        />
      </Grid2>
    </>
  );
};

export default MetadataExtendedFields;
