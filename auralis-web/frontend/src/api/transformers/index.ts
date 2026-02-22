/**
 * API Transformers
 *
 * Centralized data transformation layer that converts backend API responses
 * (snake_case) to frontend domain models (camelCase).
 *
 * This is the single source of truth for API-to-domain transformations.
 *
 * @example
 * ```typescript
 * import { transformAlbum, transformAlbumsResponse } from '@/api/transformers';
 *
 * // Transform single album
 * const album = transformAlbum(apiResponse.album);
 *
 * // Transform paginated response
 * const { albums, total, hasMore } = transformAlbumsResponse(apiResponse);
 * ```
 */

// Export all transformers
export * from './types';
export * from './albumTransformer';
export * from './artistTransformer';
export * from './trackTransformer';
export * from './playlistTransformer';
