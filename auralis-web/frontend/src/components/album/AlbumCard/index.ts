/**
 * AlbumCard Module
 *
 * Album card component with modular subcomponents for artwork management
 * Organized structure:
 * - Main component (AlbumCard.tsx)
 * - Artwork container with overlays
 * - Album info display
 * - Artwork operation handlers
 */

export { default as AlbumCard } from './AlbumCard';
export type { AlbumCardProps } from './AlbumCard';

export { ArtworkContainer } from './ArtworkContainer';
export type { ArtworkContainerProps } from './ArtworkContainer';

export { AlbumInfo } from './AlbumInfo';
export { PlayOverlay } from './PlayOverlay';
export type { PlayOverlayProps } from './PlayOverlay';

export { LoadingOverlay } from './LoadingOverlay';
export { NoArtworkButtons } from './NoArtworkButtons';
export { ArtworkMenu } from './ArtworkMenu';

export { useArtworkHandlers } from './useArtworkHandlers';
