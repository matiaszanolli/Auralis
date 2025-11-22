/**
 * Avatar Styles - Reusable avatar component styling
 *
 * Consolidates avatar styling patterns used across the application:
 * - ArtistAvatarCircle: Large 200x200 circular avatar for artist detail views
 * - ArtistSearchAvatar: Medium 40x40 avatar for search results
 * - DefaultSearchAvatar: Generic avatar for non-artist search results
 *
 * All avatars use the aurora gradient background for visual consistency.
 */

import { Avatar, Box, styled } from '@mui/material';

/**
 * ArtistAvatarCircle - Large circular artist avatar with aurora gradient background
 * Used for displaying artist initials in artist detail views
 * Dimensions: 200x200 with 5rem font size
 */
export const ArtistAvatarCircle = styled(Box)(({ theme }) => ({
  width: 200,
  height: 200,
  borderRadius: '50%',
  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '5rem',
  fontWeight: 'bold',
  color: 'white',
  boxShadow: '0 8px 32px rgba(102, 126, 234, 0.3)',
}));

/**
 * ArtistSearchAvatar - Medium avatar for artist search results
 * Features aurora gradient background with initial letter
 * Dimensions: 40x40
 */
export const ArtistSearchAvatar = styled(Avatar)(({ theme }) => ({
  width: 40,
  height: 40,
  background: 'linear-gradient(135deg, #667eea, #764ba2)',
  fontSize: '1rem',
  fontWeight: 'bold'
}));

/**
 * DefaultSearchAvatar - Generic avatar for non-artist search results
 * Used for tracks, albums, and other result types
 * Dimensions: 40x40
 */
export const DefaultSearchAvatar = styled(Avatar)(({ theme }) => ({
  width: 40,
  height: 40,
  backgroundColor: 'rgba(102, 126, 234, 0.2)'
}));
