/**
 * Animation Styles - Consolidated keyframes and animation utilities
 *
 * Centralizes all animation definitions used across the application.
 * Provides reusable keyframes for rotation, fading, pulsing, shimmering,
 * and other animation effects.
 *
 * Animations:
 * - spin: 360° rotation (1s linear)
 * - rotate: 360° rotation variant (1.4s linear)
 * - pulse: Opacity fade (2s ease-in-out)
 * - shimmer: Gradient left-to-right shimmer (2s linear)
 * - fadeIn: Opacity + scale in (300ms)
 * - float: Gentle vertical floating motion (3s ease-in-out)
 * - slideUp: Vertical slide with fade (300ms ease-out)
 */

import { keyframes } from '@mui/material';

/**
 * spin - Basic 360° rotation animation
 * Duration: 1s linear
 * Used by: Grid.styles LoadingSpinner, Skeleton spinners
 */
export const spin = keyframes`
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
`;

/**
 * rotate - 360° rotation variant with slightly longer duration
 * Duration: 1.4s linear
 * Used by: LoadingSpinner wrapper for SVG-based spinners
 */
export const rotate = keyframes`
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
`;

/**
 * pulse - Opacity fade in/out for attention drawing
 * Duration: 2s ease-in-out, infinite
 * Opacity: 1 → 0.5 (LoadingSpinner) or 1 → 0.6 (variant)
 * Used by: Loading indicators, pulsing icons, disabled states
 */
export const pulse = keyframes`
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
`;

/**
 * shimmer - Gradient left-to-right shimmer effect
 * Duration: 2s infinite linear
 * Background position: -1000px → 1000px
 * Used by: Skeleton loaders for perceived loading
 */
export const shimmer = keyframes`
  0% {
    background-position: -1000px 0;
  }
  100% {
    background-position: 1000px 0;
  }
`;

/**
 * fadeIn - Opacity + scale-in animation
 * Duration: 300ms cubic-bezier(0.4, 0, 0.2, 1)
 * Combines: opacity 0→1, scale 0.95→1
 * Used by: ProgressiveImage, image load transitions, overlay entrances
 */
export const fadeIn = keyframes`
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
`;

/**
 * float - Gentle vertical floating motion
 * Duration: 3s ease-in-out, infinite
 * Motion: translateY ±10px
 * Used by: Decorative elements, subtle hover states, hero icons
 */
export const float = keyframes`
  0%, 100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-10px);
  }
`;

/**
 * slideUp - Vertical slide with fade entrance
 * Duration: 300ms ease-out
 * Combines: translateY 10px→0, opacity 0→1
 * Used by: Modal/drawer entrances, dropdown opens, content reveals
 */
export const slideUp = keyframes`
  from {
    transform: translateY(10px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
`;
