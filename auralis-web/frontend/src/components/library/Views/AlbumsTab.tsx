
import {
  Box,
  Paper,
  Typography
} from '@mui/material';
import Grid2 from '@mui/material/Grid';
import { tokens } from '@/design-system';
import AlbumCard from '@/components/album/AlbumCard/AlbumCard';
import { themeVars } from '@/theme/semanticTheme';

interface Album {
  id: number;
  title: string;
  year?: number;
  track_count: number;
  total_duration: number;
}

interface AlbumsTabProps {
  albums: Album[];
  /** Artist name, used for each card's accessible name ("<title> by <artist>"). */
  artistName?: string;
  onAlbumClick: (albumId: number) => void;
}

/**
 * AlbumsTab - Grid of albums for artist detail view
 *
 * Displays:
 * - Album grid with artwork
 * - Album title and metadata (year, track count)
 * - Click handler for navigation
 * - Empty state message
 *
 * Renders the unified `album/AlbumCard` (which delegates to `MediaCard`) rather
 * than a local `styled(Paper)` card (#4537). The local one had `onClick` and
 * `cursor: pointer` but no `role`, `tabIndex` or `onKeyDown`, so artist -> album
 * navigation was unreachable by keyboard even though the identical flow from the
 * main library grid worked. MediaCard supplies role/tabIndex/Enter/Space and the
 * accessible name, so this deletes a duplicate rather than reimplementing
 * accessibility on the copy.
 */
export const AlbumsTab = ({
  albums,
  artistName,
  onAlbumClick
}: AlbumsTabProps) => {
  if (!albums || albums.length === 0) {
    return (
      <Paper
        sx={{
          padding: 4,
          textAlign: 'center',
          background: tokens.colors.opacityScale.white.ultraLight, // #3950
          borderRadius: 2,
        }}
      >
        <Typography sx={{
          color: "text.secondary"
        }}>
          No albums found for this artist
        </Typography>
      </Paper>
    );
  }

  return (
    <Box>
      {/* Section header with narrative cue */}
      <Box sx={{
        mb: tokens.spacing.xl,
        pb: tokens.spacing.md,
        borderBottom: `1px solid ${tokens.colors.border.light}`,
      }}>
        <Typography variant="h6" sx={{
          fontSize: tokens.typography.fontSize.lg,
          fontWeight: tokens.typography.fontWeight.semibold,
          color: themeVars.textSecondary,
          letterSpacing: '0.02em',
        }}>
          Albums {/* Sorted by year (newest first) - can be enhanced later */}
        </Typography>
      </Box>
      {/* Albums grid */}
      <Grid2 container spacing={3}>
        {albums.map((album) => (
          <Grid2
            key={album.id}
            size={{
              xs: 12,
              sm: 6,
              md: 4,
              lg: 3,
              xl: 2
            }}>
            <AlbumCard
              albumId={album.id}
              title={album.title}
              artist={artistName ?? ''}
              // `AlbumInArtist` (backend) carries no artwork flag, and the
              // AlbumArt this replaced always requested the URL and fell back to
              // a gradient on error. MediaCardArtwork does the same via onError,
              // so requesting unconditionally preserves artwork here instead of
              // forcing every album to the placeholder.
              hasArtwork
              trackCount={album.track_count}
              duration={album.total_duration}
              year={album.year}
              onClick={onAlbumClick}
            />
          </Grid2>
        ))}
      </Grid2>
    </Box>
  );
};

export default AlbumsTab;
