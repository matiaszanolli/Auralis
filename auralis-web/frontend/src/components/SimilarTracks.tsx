/**
 * SimilarTracks Component
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Displays similar tracks based on 25D audio fingerprint similarity
 *
 * Features:
 * - Shows similar tracks in a compact list
 * - Similarity percentage badges
 * - Click to play similar track
 * - Loading and error states
 * - Empty state when no similar tracks
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Chip,
  CircularProgress,
  Alert,
  Divider,
  Tooltip
} from '@mui/material';
import {
  MusicNote as MusicNoteIcon,
  AutoAwesome as SparklesIcon
} from '@mui/icons-material';
import { auroraOpacity } from './library/Color.styles';
import similarityService, { SimilarTrack } from '../services/similarityService';

interface SimilarTracksProps {
  /** Current track ID to find similar tracks for */
  trackId: number | null;
  /** Callback when user clicks on a similar track */
  onTrackSelect?: (trackId: number) => void;
  /** Number of similar tracks to show (default: 5) */
  limit?: number;
  /** Use pre-computed K-NN graph (default: true) */
  useGraph?: boolean;
}

const SimilarTracks: React.FC<SimilarTracksProps> = ({
  trackId,
  onTrackSelect,
  limit = 5,
  useGraph = true
}) => {
  const [similarTracks, setSimilarTracks] = useState<SimilarTrack[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load similar tracks when track ID changes
  useEffect(() => {
    if (!trackId) {
      setSimilarTracks([]);
      return;
    }

    loadSimilarTracks();
  }, [trackId, limit, useGraph]);

  const loadSimilarTracks = async () => {
    if (!trackId) return;

    setLoading(true);
    setError(null);

    try {
      const tracks = await similarityService.findSimilar(trackId, limit, useGraph);
      setSimilarTracks(tracks);
    } catch (err) {
      console.error('Failed to load similar tracks:', err);
      setError(err instanceof Error ? err.message : 'Failed to load similar tracks');
      setSimilarTracks([]);
    } finally {
      setLoading(false);
    }
  };

  const handleTrackClick = (track: SimilarTrack) => {
    if (onTrackSelect) {
      onTrackSelect(track.track_id);
    }
  };

  const getSimilarityColor = (score: number): string => {
    if (score >= 0.9) return '#00d4aa'; // Very similar (90%+) - turquoise
    if (score >= 0.8) return '#667eea'; // Similar (80-90%) - purple
    if (score >= 0.7) return '#764ba2'; // Somewhat similar (70-80%) - darker purple
    return '#8b92b0'; // Less similar (<70%) - gray
  };

  const formatDuration = (seconds?: number): string => {
    if (!seconds) return '';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Loading state
  if (loading) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <CircularProgress size={24} sx={{ color: '#667eea' }} />
        <Typography variant="body2" sx={{ mt: 1, color: '#8b92b0' }}>
          Finding similar tracks...
        </Typography>
      </Box>
    );
  }

  // Error state
  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error" sx={{ fontSize: '0.875rem' }}>
          {error}
        </Alert>
      </Box>
    );
  }

  // Empty state - no track selected
  if (!trackId) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <MusicNoteIcon sx={{ fontSize: 48, color: '#667eea', opacity: 0.5, mb: 1 }} />
        <Typography variant="body2" sx={{ color: '#8b92b0' }}>
          Play a track to discover similar music
        </Typography>
      </Box>
    );
  }

  // Empty state - no similar tracks found
  if (similarTracks.length === 0) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <SparklesIcon sx={{ fontSize: 48, color: '#667eea', opacity: 0.5, mb: 1 }} />
        <Typography variant="body2" sx={{ color: '#8b92b0' }}>
          No similar tracks found
        </Typography>
        <Typography variant="caption" sx={{ color: '#8b92b0', mt: 0.5, display: 'block' }}>
          Try playing a different track
        </Typography>
      </Box>
    );
  }

  // Similar tracks list
  return (
    <Box>
      {/* Header */}
      <Box sx={{ px: 2, py: 1.5, borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SparklesIcon sx={{ fontSize: 20, color: '#667eea' }} />
          <Typography variant="subtitle2" sx={{ color: '#ffffff', fontWeight: 600 }}>
            Similar Tracks
          </Typography>
        </Box>
        <Typography variant="caption" sx={{ color: '#8b92b0', mt: 0.5, display: 'block' }}>
          Based on acoustic fingerprint analysis
        </Typography>
      </Box>

      {/* Tracks List */}
      <List sx={{ p: 0 }}>
        {similarTracks.map((track, index) => (
          <React.Fragment key={track.track_id}>
            <ListItem disablePadding>
              <ListItemButton
                onClick={() => handleTrackClick(track)}
                sx={{
                  px: 2,
                  py: 1.5,
                  '&:hover': {
                    backgroundColor: auroraOpacity.veryLight
                  }
                }}
              >
                {/* Track Info */}
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography
                        variant="body2"
                        sx={{
                          color: '#ffffff',
                          fontWeight: 500,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          flex: 1
                        }}
                      >
                        {track.title}
                      </Typography>
                      {/* Similarity Badge */}
                      <Tooltip title={`${(track.similarity_score * 100).toFixed(1)}% similar`}>
                        <Chip
                          label={`${Math.round(track.similarity_score * 100)}%`}
                          size="small"
                          sx={{
                            height: 20,
                            fontSize: '0.7rem',
                            fontWeight: 600,
                            backgroundColor: getSimilarityColor(track.similarity_score),
                            color: '#ffffff',
                            '& .MuiChip-label': {
                              px: 1
                            }
                          }}
                        />
                      </Tooltip>
                    </Box>
                  }
                  secondary={
                    <Typography
                      variant="caption"
                      sx={{
                        color: '#8b92b0',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        display: 'block'
                      }}
                    >
                      {track.artist}
                      {track.duration && ` • ${formatDuration(track.duration)}`}
                    </Typography>
                  }
                />
              </ListItemButton>
            </ListItem>
            {index < similarTracks.length - 1 && (
              <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.05)' }} />
            )}
          </React.Fragment>
        ))}
      </List>

      {/* Footer Info */}
      <Box sx={{ px: 2, py: 1, borderTop: '1px solid rgba(255, 255, 255, 0.1)' }}>
        <Typography variant="caption" sx={{ color: '#8b92b0', fontSize: '0.7rem' }}>
          {useGraph ? '⚡ Fast lookup' : '🔍 Real-time search'} • {similarTracks.length} tracks
        </Typography>
      </Box>
    </Box>
  );
};

export default SimilarTracks;
