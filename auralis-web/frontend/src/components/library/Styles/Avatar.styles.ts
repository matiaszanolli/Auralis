/**
 * Avatar Styles - Reusable avatar component styling
 *
 * Consolidates avatar styling patterns used across the application:
 * - ArtistAvatarCircle: Large 200x200 circular avatar for artist detail views
 * - ArtistSearchAvatar: Medium 40x40 avatar for search results
 * - DefaultSearchAvatar: Generic avatar for non-artist search results
 *
 * All avatars use the aurora gradient background for visual consistency.
 * Shadow effects are imported from Shadow.styles.ts.
 * Border radius for circles is imported from BorderRadius.styles.ts.
 */

import { Avatar, Box, styled } from '@mui/material';
import { glowShadows } from './Shadow.styles';
import { radiusCircle } from './BorderRadius.styles';
import { gradients, auroraOpacity } from './Color.styles';
import { tokens } from '@/design-system';

/**
 * ArtistAvatarCircle - Large circular artist avatar with aurora gradient background
 * Used for displaying artist initials in artist detail views
 * Dimensions: 200x200 with 5rem font size
 */
export const ArtistAvatarCircle = styled(Box)(({ theme }) => ({
  width: 200,
  height: 200,
  borderRadius: radiusCircle,
  background: gradients.aurora,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '5rem',
  fontWeight: tokens.typography.fontWeight.bold,
  color: tokens.colors.text.primary,
  boxShadow: glowShadows.purple,
}));

/**
 * ArtistSearchAvatar - Medium avatar for artist search results
 * Features aurora gradient background with initial letter
 * Dimensions: 40x40
 */
export const ArtistSearchAvatar = styled(Avatar)(({ theme }) => ({
  width: 40,
  height: 40,
  background: gradients.aurora,
  fontSize: tokens.typography.fontSize.md,
  fontWeight: tokens.typography.fontWeight.bold
}));

/**
 * DefaultSearchAvatar - Generic avatar for non-artist search results
 * Used for tracks, albums, and other result types
 * Dimensions: 40x40
 */
export const DefaultSearchAvatar = styled(Avatar)(({ theme }) => ({
  width: 40,
  height: 40,
  backgroundColor: auroraOpacity.standard
}));
