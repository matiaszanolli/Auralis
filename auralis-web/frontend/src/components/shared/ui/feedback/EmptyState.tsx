/**
 * EmptyState - Display empty state UI with icon and message
 *
 * Main component provides flexible empty state display.
 * Predefined variants for common scenarios (EmptyLibrary, NoSearchResults, etc.)
 *
 * Styled components extracted to EmptyState.styles.ts
 */

import { ReactNode, Suspense, lazy } from 'react';
import { Box } from '@mui/material';
import MusicNote from '@mui/icons-material/MusicNote';
import SearchOff from '@mui/icons-material/SearchOff';
import PlaylistPlay from '@mui/icons-material/PlaylistPlay';
import FolderOpen from '@mui/icons-material/FolderOpen';
import { Button } from '@/design-system/primitives/Button';
import { Container, IconContainer, Title, Description } from './EmptyState.styles';

interface EmptyStateProps {
  icon?: 'music' | 'search' | 'playlist' | 'folder';
  customIcon?: ReactNode;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  /** 'alert' for a failed load, so assistive tech announces it as an error (#5870). */
  role?: 'status' | 'alert';
}

const iconMap = {
  music: MusicNote,
  search: SearchOff,
  playlist: PlaylistPlay,
  folder: FolderOpen,
};

export const EmptyState = ({
  icon = 'music',
  customIcon,
  title,
  description,
  actionLabel,
  onAction,
  role = 'status',
}: EmptyStateProps) => {
  const IconComponent = iconMap[icon];

  return (
    // role="status" announces the empty state when it appears (#5668) — the
    // "no results" / "no favorites" transitions were previously silent.
    <Container role={role}>
      <IconContainer>
        {customIcon || <IconComponent />}
      </IconContainer>

      <Title>{title}</Title>

      {description && <Description>{description}</Description>}

      {actionLabel && onAction && (
        <Button variant="primary" onClick={onAction} size="lg">
          {actionLabel}
        </Button>
      )}
    </Container>
  );
};

// Module scope on purpose: a lazy() declared in the component body is a NEW
// component type on every render, which unmounted DropZone (losing its drag
// state) and re-flashed the Loading fallback each time (#6033). Still only
// fetched when first rendered.
const DropZone = lazy(() => import('@/components/shared/DropZone/DropZone').then(m => ({ default: m.DropZone })));

// Predefined empty states for common scenarios
export const EmptyLibrary = ({ onScanFolder, onFolderDrop, scanning = false }: {
  onScanFolder?: () => void;
  onFolderDrop?: (path: string) => void;
  scanning?: boolean;
}) => {
  return (
    <Container>
      {onFolderDrop ? (
        <Suspense fallback={<div>Loading...</div>}>
          <Box sx={{ width: '100%', maxWidth: 600, mb: 4 }}>
            <DropZone
              onFolderDrop={onFolderDrop}
              onFolderSelect={onScanFolder}
              scanning={scanning}
            />
          </Box>
        </Suspense>
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
            <Button variant="primary" onClick={onScanFolder} size="lg">
              Scan Folder
            </Button>
          )}
        </>
      )}
    </Container>
  );
};

export const NoSearchResults = ({ query }: { query?: string }) => (
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

export const EmptyPlaylist = ({ onAddTracks }: { onAddTracks?: () => void }) => (
  <EmptyState
    icon="playlist"
    title="Empty playlist"
    description="This playlist doesn't have any tracks yet. Add some music to get started."
    actionLabel={onAddTracks ? "Add Tracks" : undefined}
    onAction={onAddTracks}
  />
);

export const EmptyQueue = () => (
  <EmptyState
    icon="playlist"
    title="Queue is empty"
    description="No tracks in the queue. Play a song to get started."
  />
);

export default EmptyState;
