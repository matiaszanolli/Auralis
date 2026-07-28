/**
 * API hooks for REST API communication
 * - REST API calls and data fetching
 */

// #4469: the `useQuery`/`useMutation` wrappers that used to live here were
// deleted. They had zero production consumers, shadowed the name of
// @tanstack/react-query's useQuery (which every real call site actually uses),
// and their catch blocks called setError() unconditionally — undoing the
// AbortError/StaleRequestError filtering that useRestAPI.get() performs one
// layer down (#2467, #2439). useQuery also had no unmount guard.
export { useRestAPI } from './useRestAPI';
