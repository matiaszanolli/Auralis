import React from 'react';
import { StyledTextField } from '../library/FormFields.styles';
import { DialogContentBox } from './EditPlaylistDialog.styles';

interface PlaylistFormFieldsProps {
  name: string;
  onNameChange: (value: string) => void;
  description: string;
  onDescriptionChange: (value: string) => void;
  loading: boolean;
  onKeyPress: (e: React.KeyboardEvent) => void;
}

/**
 * PlaylistFormFields - Form inputs for playlist name and description
 *
 * Displays:
 * - Name input field (required, with autofocus)
 * - Description textarea (optional)
 * - Keyboard shortcut support (Enter to save)
 */
export const PlaylistFormFields: React.FC<PlaylistFormFieldsProps> = ({
  name,
  onNameChange,
  description,
  onDescriptionChange,
  loading,
  onKeyPress,
}) => {
  return (
    <DialogContentBox>
      <StyledTextField
        autoFocus
        label="Playlist Name"
        fullWidth
        value={name}
        onChange={(e) => onNameChange(e.target.value)}
        onKeyPress={onKeyPress}
        disabled={loading}
        placeholder="Enter playlist name"
      />
      <StyledTextField
        label="Description (Optional)"
        fullWidth
        multiline
        rows={3}
        value={description}
        onChange={(e) => onDescriptionChange(e.target.value)}
        disabled={loading}
        placeholder="Add a description for your playlist"
      />
    </DialogContentBox>
  );
};

export default PlaylistFormFields;
