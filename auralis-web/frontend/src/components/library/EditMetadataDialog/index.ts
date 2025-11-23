/**
 * EditMetadataDialog Module
 *
 * Dialog for editing track metadata with modular subcomponents
 * - Main component (EditMetadataDialog.tsx)
 * - Form fields rendering (MetadataFormFields.tsx)
 * - Form state and logic (useMetadataForm.ts)
 */

export { default as EditMetadataDialog } from './EditMetadataDialog';
export type { EditMetadataDialogProps } from './EditMetadataDialog';

export { MetadataFormFields } from './MetadataFormFields';
export type { MetadataFormFieldsProps } from './MetadataFormFields';

export { useMetadataForm } from './useMetadataForm';
export type { MetadataFields } from './useMetadataForm';
