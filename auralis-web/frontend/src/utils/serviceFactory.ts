/**
 * Service Factory Pattern (Phase 5a)
 *
 * Provides a generic factory for creating CRUD services that follow common patterns.
 * Reduces code duplication across multiple simple API wrapper services.
 *
 * This factory is used by:
 * - playlistService
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
function requestOptions<T>(
  guard?: (value: unknown) => value is T,
  options?: CrudRequestOptions,
): RequestOptions<T> | undefined {
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
 *
 * `T` is the single-item shape and `TList` the shape `list()` resolves to.
 * They differ for the endpoints whose list is an envelope or a single object
 * rather than a bare array (#5637): `GET /api/playlists` answers
 * `{playlists: [...]}`, `GET /api/settings` a single settings object, and
 * `GET /api/player/queue` a single queue snapshot. Declaring the real shape
 * beats the old `Promise<T[]>` lie that every such service had to cast around.
 *
 * `C` maps each custom endpoint name to the shape it resolves to (#6052). It
 * keys `custom`, `guards.custom` and the `custom()` method, so a guard for the
 * wrong type — or a name that is not configured — fails to compile. The default
 * leaves every name `unknown` for services without custom endpoints.
 */
export interface CrudEndpoints<
  ID = number,
  P extends Record<string, unknown> = Record<string, unknown>,
  U = unknown,
  T = unknown,
  TList = T,
  C extends Record<string, unknown> = Record<string, unknown>,
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
  custom?: { [K in keyof C]?: string | ((params?: P) => string) };

  /**
   * Optional runtime shape guards for each endpoint (#4607, #5123).
   *
   * Without one, `Response.json()`'s `any` is silently narrowed to `T` and
   * backend field drift only surfaces downstream as `undefined` — the failure
   * mode behind #3593/#3976/#4440/#4441. Supplying a guard turns that into an
   * `APIRequestError` naming the endpoint.
   *
   * Each guard is a type predicate tied to that endpoint's result type
   * (#5637), so a guard asserting the wrong shape doesn't compile. The
   * `custom` guards are tied to `C[name]` the same way (#6052).
   *
   * Services without guards behave exactly as before, so adoption is incremental.
   * See `@/api/responseGuards` for the available guards.
   */
  guards?: {
    list?: (value: unknown) => value is TList;
    get?: (value: unknown) => value is T;
    create?: (value: unknown) => value is T;
    update?: (value: unknown) => value is T;
    // DELETE resolves to `void` and never reads a body (204 by contract), so
    // no meaningful guard exists — typed for symmetry only.
    delete?: (value: unknown) => value is void;
    custom?: { [K in keyof C]?: (value: unknown) => value is C[K] };
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
  TList = T,
  C extends Record<string, unknown> = Record<string, unknown>,
>(endpoints: CrudEndpoints<ID, P, U, T, TList, C>) {
  return {
    /**
     * GET list of items
     */
    async list(params?: P, options?: CrudRequestOptions): Promise<TList> {
      if (!endpoints.list) {
        throw new Error('list endpoint not configured');
      }
      const endpoint = typeof endpoints.list === 'function'
        ? endpoints.list(params)
        : endpoints.list;
      const opts = requestOptions(endpoints.guards?.list, options);
      return opts ? get<TList>(endpoint, opts) : get<TList>(endpoint);
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
      return opts ? get<T>(endpoint, opts) : get<T>(endpoint);
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
      const opts = requestOptions(endpoints.guards?.create, options);
      const body = data as Record<string, unknown>;
      return opts ? post<T>(endpoint, body, opts) : post<T>(endpoint, body);
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
      const opts = requestOptions(endpoints.guards?.update, options);
      const body = data as Record<string, unknown>;
      return opts ? put<T>(endpoint, body, opts) : put<T>(endpoint, body);
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
      const opts = requestOptions(endpoints.guards?.delete, options);
      return opts ? del(endpoint, opts) : del(endpoint);
    },

    /**
     * Custom endpoint call
     * Useful for actions that don't fit standard CRUD
     */
    async custom<K extends keyof C & string>(
      name: K,
      method: 'get' | 'post' | 'put' | 'delete',
      data?: P,
      options?: CrudRequestOptions,
    ): Promise<C[K]> {
      // Annotated: indexing `custom` by the generic `K` does not narrow on its own.
      const endpointDef: string | ((params?: P) => string) | undefined = endpoints.custom?.[name];
      if (!endpointDef) {
        throw new Error(`custom endpoint "${name}" not configured`);
      }
      const endpoint = typeof endpointDef === 'function'
        ? endpointDef(data)
        : endpointDef;
      const opts = requestOptions(endpoints.guards?.custom?.[name], options);

      const body = (data ?? {}) as Record<string, unknown>;

      switch (method) {
        case 'get':
          return opts ? get<C[K]>(endpoint, opts) : get<C[K]>(endpoint);
        case 'post':
          return opts ? post<C[K]>(endpoint, body, opts) : post<C[K]>(endpoint, body);
        case 'put':
          return opts ? put<C[K]>(endpoint, body, opts) : put<C[K]>(endpoint, body);
        case 'delete':
          return opts ? del<C[K]>(endpoint, opts) : del<C[K]>(endpoint);
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
