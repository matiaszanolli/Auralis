import React from 'react';
import { StyledTextField } from '../library/FormFields.styles';
import { DialogContentBox } from './CreatePlaylistDialog.styles';
import { InitialTracksInfo } from './InitialTracksInfo';

interface CreatePlaylistFormFieldsProps {
  name: string;
  onNameChange: (value: string) => void;
  description: string;
  onDescriptionChange: (value: string) => void;
  loading: boolean;
  onKeyPress: (e: React.KeyboardEvent) => void;
  initialTrackIds?: number[];
}

/**
 * CreatePlaylistFormFields - Form inputs for creating new playlist
 *
 * Displays:
 * - Name input field (required, with autofocus)
 * - Description textarea (optional)
 * - Initial tracks info (if tracks provided)
 * - Keyboard shortcut support (Enter to create)
 */
export const CreatePlaylistFormFields: React.FC<CreatePlaylistFormFieldsProps> = ({
  name,
  onNameChange,
  description,
  onDescriptionChange,
  loading,
  onKeyPress,
  initialTrackIds,
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
      <InitialTracksInfo trackIds={initialTrackIds} />
    </DialogContentBox>
  );
};

export default CreatePlaylistFormFields;
