/**
 * Shared prop types for CozyAlbumGrid's two virtualization strategies
 * (VirtualizedAlbumGrid, EraGroupedAlbums).
 */

export interface VirtualizedGridSharedProps {
  fingerprints: Map<number, import('@/utils/fingerprintToGradient').AudioFingerprint | null>;
  hasNextPage: boolean;
  onLoadMore: () => void;
  onAlbumClick?: (albumId: number) => void;
  onAlbumHover?: (albumId: number, albumTitle?: string, albumArtist?: string) => void;
  onAlbumHoverEnd?: () => void;
}
