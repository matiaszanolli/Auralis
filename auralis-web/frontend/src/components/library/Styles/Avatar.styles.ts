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
import { radiusCircle } from './BorderRadius.styles';
import { tokens } from '@/design-system';

/**
 * ArtistAvatarCircle - Circular artist avatar for detail views
 * Reduced prominence to avoid drawing excessive attention to placeholder
 * Dimensions: 120x120 with 3rem font size (scaled down from 200x200)
 */
export const ArtistAvatarCircle = styled(Box)(({ theme: _theme }) => ({
  width: 120,
  height: 120,
  borderRadius: radiusCircle,
  background: `linear-gradient(135deg, ${tokens.colors.bg.level3} 0%, ${tokens.colors.bg.level4} 100%)`, // Subtle gradient, not aurora
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '3rem',
  fontWeight: tokens.typography.fontWeight.semibold, // Less bold
  color: tokens.colors.text.tertiary, // More subdued
  boxShadow: 'none', // No glow effect
  border: `1px solid ${tokens.colors.border.light}`, // Subtle border
  opacity: 0.6, // Reduce visual weight
}));

/**
 * ArtistSearchAvatar - Medium avatar for artist search results
 * Features aurora gradient background with initial letter
 * Dimensions: 40x40
 */
export const ArtistSearchAvatar = styled(Avatar)(({ theme: _theme }) => ({
  width: 40,
  height: 40,
  background: tokens.gradients.aurora,
  fontSize: tokens.typography.fontSize.md,
  fontWeight: tokens.typography.fontWeight.bold
}));

/**
 * DefaultSearchAvatar - Generic avatar for non-artist search results
 * Used for tracks, albums, and other result types
 * Dimensions: 40x40
 */
export const DefaultSearchAvatar = styled(Avatar)(({ theme: _theme }) => ({
  width: 40,
  height: 40,
  backgroundColor: tokens.colors.opacityScale.accent.standard
}));
