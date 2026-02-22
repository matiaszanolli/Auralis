/**
 * Auralis Animation System
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Reusable CSS animations and keyframes for consistent motion across the application.
 * All animations should be paired with tokens.transitions for timing.
 *
 * Usage:
 * ```css
 * animation: ${animations.fadeIn.keyframes};
 * animation-duration: ${tokens.transitions.base};
 * ```
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

import { keyframes } from '@mui/material/styles';

/**
 * Fade In - Element appears with opacity transition
 */
export const fadeIn = keyframes`
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
`;

/**
 * Fade Out - Element disappears with opacity transition
 */
export const fadeOut = keyframes`
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
`;

/**
 * Slide Up - Element slides up from below
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

/**
 * Slide Down - Element slides down from above
 */
export const slideDown = keyframes`
  from {
    transform: translateY(-10px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
`;

/**
 * Slide In Right - Element slides in from the right
 */
export const slideInRight = keyframes`
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
`;

/**
 * Slide Out Right - Element slides out to the right
 */
export const slideOutRight = keyframes`
  from {
    transform: translateX(0);
    opacity: 1;
  }
  to {
    transform: translateX(100%);
    opacity: 0;
  }
`;

/**
 * Slide In Left - Element slides in from the left
 */
export const slideInLeft = keyframes`
  from {
    transform: translateX(-100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
`;

/**
 * Slide Out Left - Element slides out to the left
 */
export const slideOutLeft = keyframes`
  from {
    transform: translateX(0);
    opacity: 1;
  }
  to {
    transform: translateX(-100%);
    opacity: 0;
  }
`;

/**
 * Scale In - Element grows from center
 */
export const scaleIn = keyframes`
  from {
    transform: scale(0.95);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
`;

/**
 * Scale Out - Element shrinks to center
 */
export const scaleOut = keyframes`
  from {
    transform: scale(1);
    opacity: 1;
  }
  to {
    transform: scale(0.95);
    opacity: 0;
  }
`;

/**
 * Pulse - Subtle opacity pulse for attention
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
 * Rotate - Continuous rotation (for spinners, loaders)
 */
export const rotate = keyframes`
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
`;

/**
 * Gentle Float - Slow, weighted vertical motion
 * Style Guide §6.1: "No bounce easing" - use slow, heavy motion instead
 */
export const gentleFloat = keyframes`
  0%, 100% {
    transform: translateY(0);
    opacity: 1;
  }
  50% {
    transform: translateY(-4px);
    opacity: 0.95;
  }
`;
// Removed: deprecated 'bounce' alias (bounce = gentleFloat) — fixes #2233.
// Use 'gentleFloat' directly.

/**
 * Shimmer - Loading skeleton shimmer effect
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
 * Glow - Aurora brand color glow effect
 */
export const glow = keyframes`
  0%, 100% {
    box-shadow: 0 0 10px rgba(115, 102, 240, 0.5);
  }
  50% {
    box-shadow: 0 0 20px rgba(115, 102, 240, 0.8);
  }
`;

/**
 * Glow Aqua - Electric Aqua secondary glow
 */
export const glowAqua = keyframes`
  0%, 100% {
    box-shadow: 0 0 10px rgba(71, 214, 255, 0.5);
  }
  50% {
    box-shadow: 0 0 20px rgba(71, 214, 255, 0.8);
  }
`;

/**
 * Breathe - Slow, organic scale animation
 * Style Guide §6.1: Slow, heavy motion that "responds to audio like breathing"
 * Use with 2-3s duration for ambient effects
 */
export const breathe = keyframes`
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.02);
    opacity: 0.92;
  }
`;

/**
 * Weighted Lift - Slow vertical motion for attention
 * Style Guide §6.1: "Motion should feel like moving through liquid"
 * Use instead of bounce for call-to-action elements
 */
export const weightedLift = keyframes`
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-3px);
  }
`;
