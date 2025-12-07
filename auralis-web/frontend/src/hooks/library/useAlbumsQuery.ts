/**
 * useAlbumsQuery - Placeholder stub for album query hook
 * TODO: Implement full album pagination functionality
 * Currently returns empty data to allow build to proceed
 */

export function useAlbumsQuery(options?: { limit?: number }) {
  return {
    data: [],
    isLoading: false,
    error: null,
    total: 0,
    hasMore: false,
    fetchMore: () => {},
  };
}
