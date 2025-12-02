/**
 * Library Styles Module
 *
 * Centralized style exports for library components:
 * - Animation, ArtistDetail, ArtistList - Animation and layout styles
 * - Avatar, Button, Color, Container - UI element styles
 * - Dialog, EmptyState, FormFields - Dialog and form styles
 * - Grid, Icon, Skeleton, Spinner - Grid and loading styles
 * - Shadow, Spacing, Table, Tabs - Layout and container styles
 * - Typography, TrackRow, SearchStyles - Text and specific component styles
 * - BorderRadius - Border radius constants
 */

export * from './Animation.styles';
export * from './Avatar.styles';
export * from './BorderRadius.styles';
export * from './Button.styles';
export * from './Color.styles';
export * from './Container.styles';
export * from './EmptyState.styles';
export * from './FormFields.styles';
export * from './Grid.styles';
export * from './Icon.styles';
export * from './SearchStyles.styles';
export * from './Shadow.styles';
export * from './Skeleton.styles';
export * from './Spacing.styles';
export * from './Spinner.styles';
export * from './Table.styles';
export * from './Tabs.styles';
export * from './Typography.styles';

// Component-specific styles (avoid re-exporting to prevent conflicts)
export { DetailViewTabs as StyledTabs, DetailViewTabs } from './ArtistDetail.styles';
export { DialogTabs } from './Dialog.styles';
export { StyledListItemButton, ArtistListContainer, LoadMoreTrigger, EndOfListIndicator } from './ArtistList.styles';
