/**
 * Service Factory Pattern (Phase 5a)
 *
 * Provides a generic factory for creating CRUD services that follow common patterns.
 * Reduces code duplication across multiple simple API wrapper services.
 *
 * This factory is used by:
 * - playlistService
 * - queueService
 * - settingsService
 * - artworkService
 * - And other similar REST API wrapper services
 *
 * Benefits:
 * - DRY principle: Common CRUD logic defined once
 * - Type safety: Generic types for all operations
 * - Consistency: All services follow same patterns
 * - Maintainability: Changes to common operations affect all services
 */

import { get, post, put, del, type RequestOptions } from './apiRequest';

/**
 * Per-call options accepted by every generated CRUD method (#4614).
 *
 * Narrowed to `signal` on purpose. Widening this to the full `RequestOptions`
 * would let a caller pass `validate` and silently override the endpoint's
 * configured `guards`, defeating the runtime shape checks added in #4607.
 * Cancellation is the capability the factory was missing; nothing else.
 */
export type CrudRequestOptions = Pick<RequestOptions, 'signal'>;

/**
 * Build the options object handed to `get`/`post`/`put`/`del`.
 *
 * Returns `undefined` when there is nothing to pass. Callers below then omit
 * the argument entirely rather than passing an explicit `undefined`, so
 * services with neither a guard nor a signal keep the exact previous call
 * *arity* — the property #4607 established, which the existing
 * `playlistService` tests assert via `toHaveBeenCalledWith(url)`.
 */
function requestOptions(
  guard?: (value: unknown) => boolean,
  options?: CrudRequestOptions,
): RequestOptions | undefined {
  if (!guard && !options?.signal) return undefined;
  return {
    ...(options?.signal ? { signal: options.signal } : {}),
    ...(guard ? { validate: guard } : {}),
  };
}

/**
 * Generic CRUD endpoint configuration.
 *
 * #3595: generic ID parameter so each derived service can declare its ID
 * type (e.g. number for playlists/tracks, string for fingerprints) and
 * passing a string where a number is expected becomes a TS error.
 */
export interface CrudEndpoints<
  ID = number,
  P extends Record<string, unknown> = Record<string, unknown>,
  U = unknown,
> {
  list?: string | ((params?: P) => string);
  get?: string | ((id: ID) => string);
  // create/update URL-builders receive the request body, not `P` (URL/query
  // params) — `P` and the body shape are unrelated types (e.g.
  // PlaylistListParams vs Playlist) and forcing them together required an
  // `unknown` double-cast that let the actual body slip through unchecked (#4461).
  create?: string | ((data?: Partial<U>) => string);
  update?: string | ((id: ID, data?: Partial<U>) => string);
  delete?: string | ((id: ID) => string);
  custom?: Record<string, string | ((params?: P) => string)>;

  /**
   * Optional runtime shape guards for the read endpoints (#4607).
   *
   * Without one, `Response.json()`'s `any` is silently narrowed to `T` and
   * backend field drift only surfaces downstream as `undefined` — the failure
   * mode behind #3593/#3976/#4440/#4441. Supplying a guard turns that into an
   * `APIRequestError` naming the endpoint.
   *
   * Services without guards behave exactly as before, so adoption is incremental.
   * See `@/api/responseGuards` for the available guards.
   */
  guards?: {
    list?: (value: unknown) => boolean;
    get?: (value: unknown) => boolean;
  };
}

/**
 * Generic service factory for creating REST API wrapper services
 *
 * @param endpoints Configuration object with endpoint paths
 * @returns Object with generic CRUD functions
 */
export function createCrudService<
  T = unknown,
  U = unknown,
  ID = number,
  P extends Record<string, unknown> = Record<string, unknown>,
>(endpoints: CrudEndpoints<ID, P, U>) {
  return {
    /**
     * GET list of items
     */
    async list(params?: P, options?: CrudRequestOptions): Promise<T[]> {
      if (!endpoints.list) {
        throw new Error('list endpoint not configured');
      }
      const endpoint = typeof endpoints.list === 'function'
        ? endpoints.list(params)
        : endpoints.list;
      const opts = requestOptions(endpoints.guards?.list, options);
      return opts ? get(endpoint, opts) : get(endpoint);
    },

    /**
     * GET single item by ID
     */
    async getOne(id: ID, options?: CrudRequestOptions): Promise<T> {
      if (!endpoints.get) {
        throw new Error('get endpoint not configured');
      }
      const endpoint = typeof endpoints.get === 'function'
        ? endpoints.get(id)
        : endpoints.get;
      const opts = requestOptions(endpoints.guards?.get, options);
      return opts ? get(endpoint, opts) : get(endpoint);
    },

    /**
     * POST create new item
     */
    async create(data: U, options?: CrudRequestOptions): Promise<T> {
      if (!endpoints.create) {
        throw new Error('create endpoint not configured');
      }
      const endpoint = typeof endpoints.create === 'function'
        ? endpoints.create(data)
        : endpoints.create;
      const opts = requestOptions(undefined, options);
      const body = data as Record<string, unknown>;
      return opts ? post(endpoint, body, opts) : post(endpoint, body);
    },

    /**
     * PUT update existing item
     */
    async update(id: ID, data: Partial<U>, options?: CrudRequestOptions): Promise<T> {
      if (!endpoints.update) {
        throw new Error('update endpoint not configured');
      }
      const endpoint = typeof endpoints.update === 'function'
        ? endpoints.update(id, data)
        : endpoints.update;
      const opts = requestOptions(undefined, options);
      const body = data as Record<string, unknown>;
      return opts ? put(endpoint, body, opts) : put(endpoint, body);
    },

    /**
     * DELETE item by ID
     */
    async delete(id: ID, options?: CrudRequestOptions): Promise<void> {
      if (!endpoints.delete) {
        throw new Error('delete endpoint not configured');
      }
      const endpoint = typeof endpoints.delete === 'function'
        ? endpoints.delete(id)
        : endpoints.delete;
      const opts = requestOptions(undefined, options);
      return opts ? del(endpoint, opts) : del(endpoint);
    },

    /**
     * Custom endpoint call
     * Useful for actions that don't fit standard CRUD
     */
    async custom<R = unknown>(
      name: string,
      method: 'get' | 'post' | 'put' | 'delete',
      data?: P,
      options?: CrudRequestOptions,
    ): Promise<R> {
      if (!endpoints.custom || !endpoints.custom[name]) {
        throw new Error(`custom endpoint "${name}" not configured`);
      }
      const endpointDef = endpoints.custom[name];
      const endpoint = typeof endpointDef === 'function'
        ? endpointDef(data)
        : endpointDef;
      const opts = requestOptions(undefined, options);

      const body = (data ?? {}) as Record<string, unknown>;

      switch (method) {
        case 'get':
          return opts ? get<R>(endpoint, opts) : get<R>(endpoint);
        case 'post':
          return opts ? post<R>(endpoint, body, opts) : post<R>(endpoint, body);
        case 'put':
          return opts ? put<R>(endpoint, body, opts) : put<R>(endpoint, body);
        case 'delete':
          return opts ? del<R>(endpoint, opts) : del<R>(endpoint);
        default:
          throw new Error(`Unknown HTTP method: ${method}`);
      }
    },

    /**
     * Batch operations
     *
     * One signal cancels the whole batch — `Promise.all` rejects on the first
     * abort, which is the intended unmount/supersession behaviour.
     */
    async batchCreate(items: U[], options?: CrudRequestOptions): Promise<T[]> {
      return Promise.all(items.map(item => this.create(item, options)));
    },

    async batchDelete(ids: ID[], options?: CrudRequestOptions): Promise<void> {
      return Promise.all(ids.map(id => this.delete(id, options))).then(() => undefined);
    }
  };
}

/**
 * Helper to create endpoint URL generator
 * Used for dynamic endpoints that require IDs
 */
export function createEndpointGenerator(baseUrl: string) {
  return {
    withId: (id: any) => `${baseUrl}/${id}`,
    withParam: (key: string, value: any) => `${baseUrl}?${key}=${value}`,
    withParams: (params: Record<string, any>) => {
      const queryString = Object.entries(params)
        .map(([k, v]: [string, any]) => `${k}=${v}`)
        .join('&');
      return queryString ? `${baseUrl}?${queryString}` : baseUrl;
    }
  };
}
