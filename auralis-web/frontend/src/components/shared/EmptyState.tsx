import React from 'react';
import { Box, Typography, styled } from '@mui/material';
import { MusicNote, SearchOff, PlaylistPlay, FolderOpen } from '@mui/icons-material';
import { colors, spacing, transitions } from '../../theme/auralisTheme';
import { GradientButton } from './GradientButton';

interface EmptyStateProps {
  icon?: 'music' | 'search' | 'playlist' | 'folder';
  customIcon?: React.ReactNode;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}

const Container = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  padding: `${spacing.xxxl}px ${spacing.xl}px`,
  textAlign: 'center',
  minHeight: '300px',
});

const IconContainer = styled(Box)({
  marginBottom: `${spacing.lg}px`,
  '& .MuiSvgIcon-root': {
    fontSize: '80px',
    color: 'rgba(102, 126, 234, 0.3)',
    transition: `all ${transitions.normal}`,
  },

  '&:hover .MuiSvgIcon-root': {
    color: 'rgba(102, 126, 234, 0.5)',
    transform: 'scale(1.1)',
  },
});

const Title = styled(Typography)({
  fontSize: '24px',
  fontWeight: 600,
  color: colors.text.primary,
  marginBottom: `${spacing.sm}px`,
});

const Description = styled(Typography)({
  fontSize: '14px',
  color: colors.text.secondary,
  marginBottom: `${spacing.lg}px`,
  maxWidth: '400px',
  lineHeight: 1.6,
});

const iconMap = {
  music: MusicNote,
  search: SearchOff,
  playlist: PlaylistPlay,
  folder: FolderOpen,
};

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon = 'music',
  customIcon,
  title,
  description,
  actionLabel,
  onAction,
}) => {
  const IconComponent = iconMap[icon];

  return (
    <Container>
      <IconContainer>
        {customIcon || <IconComponent />}
      </IconContainer>

      <Title>{title}</Title>

      {description && <Description>{description}</Description>}

      {actionLabel && onAction && (
        <GradientButton onClick={onAction} size="large">
          {actionLabel}
        </GradientButton>
      )}
    </Container>
  );
};

// Predefined empty states for common scenarios
export const EmptyLibrary: React.FC<{
  onScanFolder?: () => void;
  onFolderDrop?: (path: string) => void;
  scanning?: boolean;
}> = ({ onScanFolder, onFolderDrop, scanning = false }) => {
  // Only import DropZone if needed
  const DropZone = React.lazy(() => import('./DropZone').then(m => ({ default: m.DropZone })));

  return (
    <Container>
      {onFolderDrop ? (
        <React.Suspense fallback={<div>Loading...</div>}>
          <Box sx={{ width: '100%', maxWidth: 600, mb: 4 }}>
            <DropZone
              onFolderDrop={onFolderDrop}
              onFolderSelect={onScanFolder}
              scanning={scanning}
            />
          </Box>
        </React.Suspense>
      ) : (
        <>
          <IconContainer>
            <MusicNote />
          </IconContainer>
          <Title>No music yet</Title>
          <Description>
            Your library is empty. Start by scanning a folder to add your music collection.
          </Description>
          {onScanFolder && (
            <GradientButton onClick={onScanFolder} size="large">
              Scan Folder
            </GradientButton>
          )}
        </>
      )}
    </Container>
  );
};

export const NoSearchResults: React.FC<{ query?: string }> = ({ query }) => (
  <EmptyState
    icon="search"
    title="No results found"
    description={
      query
        ? `No tracks match "${query}". Try adjusting your search terms.`
        : 'Try adjusting your search terms.'
    }
  />
);

export const EmptyPlaylist: React.FC<{ onAddTracks?: () => void }> = ({ onAddTracks }) => (
  <EmptyState
    icon="playlist"
    title="Empty playlist"
    description="This playlist doesn't have any tracks yet. Add some music to get started."
    actionLabel={onAddTracks ? "Add Tracks" : undefined}
    onAction={onAddTracks}
  />
);

export const EmptyQueue: React.FC = () => (
  <EmptyState
    icon="playlist"
    title="Queue is empty"
    description="No tracks in the queue. Play a song to get started."
  />
);

export default EmptyState;
