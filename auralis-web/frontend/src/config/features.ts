/**
 * Feature Flags for Auralis
 *
 * Enable/disable experimental features for testing and gradual rollout.
 */

export const FEATURES = {
  /**
   * MSE (Media Source Extensions) for progressive streaming
   *
   * When enabled:
   * - Uses MSE-based progressive chunk loading
   * - Instant preset switching (< 100ms with cache)
   * - Multi-tier buffer integration
   *
   * When disabled:
   * - Falls back to HTML5 audio with full files
   * - Slower preset switching (2-5s)
   */
  MSE_STREAMING: true,

  /**
   * Debug logging for MSE
   */
  MSE_DEBUG: true,
} as const;

/**
 * Check if a feature is enabled
 */
export function isFeatureEnabled(feature: keyof typeof FEATURES): boolean {
  return FEATURES[feature] === true;
}

/**
 * Get all enabled features
 */
export function getEnabledFeatures(): string[] {
  return Object.entries(FEATURES)
    .filter(([_, enabled]) => enabled)
    .map(([feature, _]) => feature);
}
