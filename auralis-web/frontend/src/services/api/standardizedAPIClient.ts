/**
 * Cache telemetry types and shape guards
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * What remains of the former `StandardizedAPIClient`, the app's third parallel
 * HTTP layer, retired by #4693. The client, `CacheAwareAPIClient`, the
 * singleton accessors and the `SuccessResponse`/`ErrorResponse` envelope all
 * went with it; `hooks/shared/useStandardizedAPI.ts` now calls
 * `utils/apiRequest.ts` directly and passes the two guards below as its
 * `validate` step.
 *
 * The envelope types and their `isSuccessResponse`/`isErrorResponse` guards
 * were dropped rather than ported. #4693's completeness check asks that they
 * be carried over, but there was nothing to carry: no production code ever
 * called them, and the client's own comment recorded the envelope as
 * "currently unused" because these endpoints return their payload bare. Their
 * only exercise was a test asserting they take `unknown` rather than `any`
 * (#4664), which is a property of code that no longer exists.
 *
 * The file keeps its name because six modules import `CacheStats` /
 * `CacheHealth` from this path. Renaming it to match its contents is a
 * mechanical follow-up, not part of the retirement.
 *
 * New guards belong in `@/api/responseGuards`, which generalised this
 * #4440 pattern for every other endpoint.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

export interface CacheStats {
  tier1: {
    chunks: number;
    size_mb: number;
    hits: number;
    misses: number;
    hit_rate: number;
  };
  tier2: {
    chunks: number;
    size_mb: number;
    hits: number;
    misses: number;
    hit_rate: number;
  };
  overall: {
    total_chunks: number;
    total_size_mb: number;
    total_hits: number;
    total_misses: number;
    overall_hit_rate: number;
    tracks_cached: number;
  };
  tracks: Record<string, {
    track_id: number;
    completion_percent: number;
    fully_cached: boolean;
  }>;
}

/**
 * Cache health response
 */
export interface CacheHealth {
  healthy: boolean;
  tier1_size_mb: number;
  tier1_healthy: boolean;
  tier2_size_mb: number;
  tier2_healthy: boolean;
  total_size_mb: number;
  memory_healthy: boolean;
  tier1_hit_rate: number;
  overall_hit_rate: number;
  /** Optional: the /api/cache/health endpoint does not currently emit this (#4440). */
  timestamp?: string;
}

/**
 * Runtime shape check for a bare CacheStats payload (#4440). The
 * /api/cache/stats endpoint returns this object directly, NOT wrapped in a
 * SuccessResponse envelope.
 */
export function isCacheStatsShape(v: unknown): v is CacheStats {
  if (!v || typeof v !== 'object') return false;
  const o = v as Record<string, unknown>;
  return (
    typeof o.tier1 === 'object' && o.tier1 !== null &&
    typeof o.tier2 === 'object' && o.tier2 !== null &&
    typeof o.overall === 'object' && o.overall !== null
  );
}

/**
 * Runtime shape check for a bare CacheHealth payload (#4440). The
 * /api/cache/health endpoint returns this dict directly (and without a
 * `timestamp`), NOT wrapped in a SuccessResponse envelope.
 */
export function isCacheHealthShape(v: unknown): v is CacheHealth {
  if (!v || typeof v !== 'object') return false;
  const o = v as Record<string, unknown>;
  return typeof o.healthy === 'boolean' && typeof o.total_size_mb === 'number';
}

/**
 * Unwrap a cache-endpoint response into its typed payload (#4440).
 *
 * These endpoints return the payload BARE (no `{status,data}` envelope), so the
 * old `isSuccessResponse` gate (`status === 'success'`) never matched and every
 * 200 OK resolved to `null`. This accepts both a bare payload and (defensively)
 * a wrapped one, throws on a genuine ErrorResponse from `request()`, and throws
 * on an unrecognized shape — surfacing a real error instead of a silent null.
 */
