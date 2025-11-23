/**
 * ArtistDetailHeader Component
 *
 * Header section with back button and artist info
 */

import React from 'react';
import { Box, Container, Button, IconButton } from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import ArtistHeader from './ArtistHeader';

interface Track {
  id: number;
  title: string;
  album: string;
  duration: number;
  track_number?: number;
}

interface Album {
  id: number;
  title: string;
  year?: number;
  track_count: number;
  total_duration: number;
}

interface Artist {
  id: number;
  name: string;
  album_count?: number;
  track_count?: number;
  albums?: Album[];
  tracks?: Track[];
}

interface ArtistDetailHeaderProps {
  artist: Artist;
  onBack?: () => void;
  onPlayAll: () => void;
  onShuffle: () => void;
}

export const ArtistDetailHeaderSection: React.FC<ArtistDetailHeaderProps> = ({
  artist,
  onBack,
  onPlayAll,
  onShuffle,
}) => {
  return (
    <>
      {onBack && (
        <IconButton
          onClick={onBack}
          sx={{
            mb: 2,
            '&:hover': {
              backgroundColor: 'rgba(255,255,255,0.1)',
            },
          }}
        >
          <ArrowBack />
        </IconButton>
      )}

      <ArtistHeader
        artist={artist}
        onPlayAll={onPlayAll}
        onShuffle={onShuffle}
      />
    </>
  );
};
