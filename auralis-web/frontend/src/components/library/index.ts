/**
 * Library Module (Main Barrel Export)
 *
 * Organized structure with submodules:
 * - Views/ - Main library view components (Albums, Tracks, etc.)
 * - Search/ - Search functionality components
 * - Items/ - Item/row/card components and loading states
 * - Details/ - Album and artist detail views
 * - Controls/ - Library header and batch actions
 * - Styles/ - Centralized style exports
 * - Hooks/ - Custom hooks for library components
 * - EditMetadataDialog/ - Metadata editing dialog module
 *
 * Main Components (at library root):
 * - CozyLibraryView - Main library container component
 */

// Main library view component
export { default as CozyLibraryView } from './CozyLibraryView';

// Views submodule
export {
  AlbumsTab,
  TracksTab,
  TrackListView,
  LibraryViewRouter,
} from './Views';

// Search submodule
export {
  GlobalSearch,
  SearchInput,
  SearchResultItem,
  ResultGroup,
  ResultsContainer,
  ResultAvatar,
} from './Search';

// Items submodule
export {
  TrackRow,
  DraggableTrackRow,
  SelectableTrackRow,
  ArtistListItem,
  ArtistSection,
  CozyAlbumGrid,
  CozyArtistList,
  AlbumTrackTable,
  ArtistListLoading,
  GridLoadingState,
  EndOfListIndicator,
  InfiniteScrollTrigger,
} from './Items';

// Details submodule
export {
  AlbumDetailView,
  ArtistDetailView,
  DetailViewHeader,
  DetailLoading,
  ArtistHeader,
} from './Details';

// Controls submodule
export {
  LibraryHeader,
  BatchActionsToolbar,
} from './Controls';

// Styles submodule
export * from './Styles';

// Hooks submodule
export {
  useSearchLogic,
} from './Hooks';

// EditMetadataDialog submodule
export {
  EditMetadataDialog,
  MetadataFormFields,
  useMetadataForm,
} from './EditMetadataDialog';
