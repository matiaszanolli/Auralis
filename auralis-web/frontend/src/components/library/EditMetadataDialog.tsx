import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Grid,
  CircularProgress,
  Alert,
  Box,
  Typography
} from '@mui/material';
import {
  Save as SaveIcon,
  Close as CloseIcon
} from '@mui/icons-material';

interface MetadataFields {
  title?: string;
  artist?: string;
  album?: string;
  albumartist?: string;
  year?: number | string;
  genre?: string;
  track?: number | string;
  disc?: number | string;
  comment?: string;
  bpm?: number | string;
  composer?: string;
  publisher?: string;
}

interface EditMetadataDialogProps {
  open: boolean;
  trackId: number;
  currentMetadata?: MetadataFields;
  onClose: () => void;
  onSave?: (trackId: number, metadata: MetadataFields) => void;
}

const EditMetadataDialog: React.FC<EditMetadataDialogProps> = ({
  open,
  trackId,
  currentMetadata,
  onClose,
  onSave
}) => {
  const [metadata, setMetadata] = useState<MetadataFields>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Load current metadata when dialog opens
  useEffect(() => {
    if (open && trackId) {
      if (currentMetadata) {
        setMetadata(currentMetadata);
      } else {
        fetchMetadata();
      }
    }
  }, [open, trackId, currentMetadata]);

  const fetchMetadata = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/metadata/tracks/${trackId}`);

      if (!response.ok) {
        throw new Error('Failed to fetch metadata');
      }

      const data = await response.json();
      setMetadata(data.metadata || {});
    } catch (err) {
      console.error('Error fetching metadata:', err);
      setError(err instanceof Error ? err.message : 'Failed to load metadata');
    } finally {
      setLoading(false);
    }
  };

  const handleFieldChange = (field: keyof MetadataFields, value: string) => {
    setMetadata(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);

    try {
      // Filter out empty values and convert numbers
      const updates: Partial<MetadataFields> = {};
      Object.entries(metadata).forEach(([key, value]) => {
        if (value !== undefined && value !== '') {
          // Convert numeric fields
          if (['year', 'track', 'disc', 'bpm'].includes(key)) {
            const num = parseInt(String(value), 10);
            if (!isNaN(num)) {
              updates[key as keyof MetadataFields] = num;
            }
          } else {
            updates[key as keyof MetadataFields] = value;
          }
        }
      });

      if (Object.keys(updates).length === 0) {
        setError('No changes to save');
        setSaving(false);
        return;
      }

      const response = await fetch(`/api/metadata/tracks/${trackId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(updates)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save metadata');
      }

      const result = await response.json();
      setSuccess(true);

      // Call onSave callback if provided
      if (onSave) {
        onSave(trackId, updates);
      }

      // Close dialog after a brief delay to show success message
      setTimeout(() => {
        onClose();
      }, 1000);

    } catch (err) {
      console.error('Error saving metadata:', err);
      setError(err instanceof Error ? err.message : 'Failed to save metadata');
    } finally {
      setSaving(false);
    }
  };

  const handleClose = () => {
    if (!saving) {
      setError(null);
      setSuccess(false);
      onClose();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: '#1a1f3a',
          backgroundImage: 'linear-gradient(135deg, #1a1f3a 0%, #0f1228 100%)',
        }
      }}
    >
      <DialogTitle sx={{ color: '#fff', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Typography variant="h6">Edit Metadata</Typography>
          {loading && <CircularProgress size={24} />}
        </Box>
      </DialogTitle>

      <DialogContent sx={{ mt: 2 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {success && (
          <Alert severity="success" sx={{ mb: 2 }}>
            Metadata saved successfully!
          </Alert>
        )}

        {loading ? (
          <Box display="flex" justifyContent="center" p={4}>
            <CircularProgress />
          </Box>
        ) : (
          <Grid container spacing={2}>
            {/* Title */}
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Title"
                value={metadata.title || ''}
                onChange={(e) => handleFieldChange('title', e.target.value)}
                variant="outlined"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: '#fff',
                    '& fieldset': { borderColor: 'rgba(255,255,255,0.2)' },
                    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                    '&.Mui-focused fieldset': { borderColor: '#667eea' }
                  },
                  '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' }
                }}
              />
            </Grid>

            {/* Artist */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Artist"
                value={metadata.artist || ''}
                onChange={(e) => handleFieldChange('artist', e.target.value)}
                variant="outlined"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: '#fff',
                    '& fieldset': { borderColor: 'rgba(255,255,255,0.2)' },
                    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                    '&.Mui-focused fieldset': { borderColor: '#667eea' }
                  },
                  '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' }
                }}
              />
            </Grid>

            {/* Album Artist */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Album Artist"
                value={metadata.albumartist || ''}
                onChange={(e) => handleFieldChange('albumartist', e.target.value)}
                variant="outlined"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: '#fff',
                    '& fieldset': { borderColor: 'rgba(255,255,255,0.2)' },
                    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                    '&.Mui-focused fieldset': { borderColor: '#667eea' }
                  },
                  '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' }
                }}
              />
            </Grid>

            {/* Album */}
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Album"
                value={metadata.album || ''}
                onChange={(e) => handleFieldChange('album', e.target.value)}
                variant="outlined"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: '#fff',
                    '& fieldset': { borderColor: 'rgba(255,255,255,0.2)' },
                    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                    '&.Mui-focused fieldset': { borderColor: '#667eea' }
                  },
                  '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' }
                }}
              />
            </Grid>

            {/* Genre */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Genre"
                value={metadata.genre || ''}
                onChange={(e) => handleFieldChange('genre', e.target.value)}
                variant="outlined"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: '#fff',
                    '& fieldset': { borderColor: 'rgba(255,255,255,0.2)' },
                    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                    '&.Mui-focused fieldset': { borderColor: '#667eea' }
                  },
                  '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' }
                }}
              />
            </Grid>

            {/* Year */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Year"
                type="number"
                value={metadata.year || ''}
                onChange={(e) => handleFieldChange('year', e.target.value)}
                variant="outlined"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: '#fff',
                    '& fieldset': { borderColor: 'rgba(255,255,255,0.2)' },
                    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                    '&.Mui-focused fieldset': { borderColor: '#667eea' }
                  },
                  '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' }
                }}
              />
            </Grid>

            {/* Track Number */}
            <Grid item xs={6} sm={3}>
              <TextField
                fullWidth
                label="Track #"
                type="number"
                value={metadata.track || ''}
                onChange={(e) => handleFieldChange('track', e.target.value)}
                variant="outlined"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: '#fff',
                    '& fieldset': { borderColor: 'rgba(255,255,255,0.2)' },
                    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                    '&.Mui-focused fieldset': { borderColor: '#667eea' }
                  },
                  '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' }
                }}
              />
            </Grid>

            {/* Disc Number */}
            <Grid item xs={6} sm={3}>
              <TextField
                fullWidth
                label="Disc #"
                type="number"
                value={metadata.disc || ''}
                onChange={(e) => handleFieldChange('disc', e.target.value)}
                variant="outlined"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: '#fff',
                    '& fieldset': { borderColor: 'rgba(255,255,255,0.2)' },
                    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                    '&.Mui-focused fieldset': { borderColor: '#667eea' }
                  },
                  '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' }
                }}
              />
            </Grid>

            {/* Composer */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Composer"
                value={metadata.composer || ''}
                onChange={(e) => handleFieldChange('composer', e.target.value)}
                variant="outlined"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: '#fff',
                    '& fieldset': { borderColor: 'rgba(255,255,255,0.2)' },
                    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                    '&.Mui-focused fieldset': { borderColor: '#667eea' }
                  },
                  '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' }
                }}
              />
            </Grid>

            {/* Comment */}
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Comment"
                value={metadata.comment || ''}
                onChange={(e) => handleFieldChange('comment', e.target.value)}
                multiline
                rows={3}
                variant="outlined"
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: '#fff',
                    '& fieldset': { borderColor: 'rgba(255,255,255,0.2)' },
                    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
                    '&.Mui-focused fieldset': { borderColor: '#667eea' }
                  },
                  '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' }
                }}
              />
            </Grid>
          </Grid>
        )}
      </DialogContent>

      <DialogActions sx={{ borderTop: '1px solid rgba(255,255,255,0.1)', p: 2 }}>
        <Button
          onClick={handleClose}
          disabled={saving}
          startIcon={<CloseIcon />}
          sx={{
            color: 'rgba(255,255,255,0.7)',
            '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' }
          }}
        >
          Cancel
        </Button>
        <Button
          onClick={handleSave}
          disabled={saving || loading}
          variant="contained"
          startIcon={saving ? <CircularProgress size={16} /> : <SaveIcon />}
          sx={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            '&:hover': {
              background: 'linear-gradient(135deg, #7c8ef5 0%, #8b5bb3 100%)',
            }
          }}
        >
          {saving ? 'Saving...' : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default EditMetadataDialog;
