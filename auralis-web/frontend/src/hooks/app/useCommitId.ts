/**
 * Hook to access the current commit ID
 * Useful for debugging and verifying which version is running
 * @returns Short commit hash (e.g., "1ef3bb0")
 */
export function useCommitId(): string {
  return import.meta.env.VITE_COMMIT_ID || 'unknown'
}

/**
 * Get the full version string for display
 * @returns Version string like "beta.13-1ef3bb0"
 */
export function getVersionString(): string {
  const commitId = import.meta.env.VITE_COMMIT_ID || 'unknown'
  const version = '1.0.0-beta.13'
  return `${version} (${commitId})`
}
