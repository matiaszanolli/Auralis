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

import { get, post, put, del } from './apiRequest';

/**
 * Generic CRUD endpoint configuration.
 *
 * #3595: generic ID parameter so each derived service can declare its ID
 * type (e.g. number for playlists/tracks, string for fingerprints) and
 * passing a string where a number is expected becomes a TS error.
 */
export interface CrudEndpoints<ID = number, P extends Record<string, unknown> = Record<string, unknown>> {
  list?: string | ((params?: P) => string);
  get?: string | ((id: ID) => string);
  create?: string | ((params?: P) => string);
  update?: string | ((id: ID, params?: P) => string);
  delete?: string | ((id: ID) => string);
  custom?: Record<string, string | ((params?: P) => string)>;
}

/**
 * Generic service factory for creating REST API wrapper services
 *
 * @param endpoints Configuration object with endpoint paths
 * @returns Object with generic CRUD functions
 */
export function createCrudService<
  T = unknown,
  U extends Record<string, unknown> = Record<string, unknown>,
  ID = number,
  P extends Record<string, unknown> = Record<string, unknown>,
>(endpoints: CrudEndpoints<ID, P>) {
  return {
    /**
     * GET list of items
     */
    async list(params?: P): Promise<T[]> {
      if (!endpoints.list) {
        throw new Error('list endpoint not configured');
      }
      const endpoint = typeof endpoints.list === 'function'
        ? endpoints.list(params)
        : endpoints.list;
      return get(endpoint);
    },

    /**
     * GET single item by ID
     */
    async getOne(id: ID): Promise<T> {
      if (!endpoints.get) {
        throw new Error('get endpoint not configured');
      }
      const endpoint = typeof endpoints.get === 'function'
        ? endpoints.get(id)
        : endpoints.get;
      return get(endpoint);
    },

    /**
     * POST create new item
     */
    async create(data: U): Promise<T> {
      if (!endpoints.create) {
        throw new Error('create endpoint not configured');
      }
      const endpoint = typeof endpoints.create === 'function'
        ? endpoints.create(data as unknown as P)
        : endpoints.create;
      return post(endpoint, data);
    },

    /**
     * PUT update existing item
     */
    async update(id: ID, data: Partial<U>): Promise<T> {
      if (!endpoints.update) {
        throw new Error('update endpoint not configured');
      }
      const endpoint = typeof endpoints.update === 'function'
        ? endpoints.update(id, data as unknown as P)
        : endpoints.update;
      return put(endpoint, data);
    },

    /**
     * DELETE item by ID
     */
    async delete(id: ID): Promise<void> {
      if (!endpoints.delete) {
        throw new Error('delete endpoint not configured');
      }
      const endpoint = typeof endpoints.delete === 'function'
        ? endpoints.delete(id)
        : endpoints.delete;
      return del(endpoint);
    },

    /**
     * Custom endpoint call
     * Useful for actions that don't fit standard CRUD
     */
    async custom(name: string, method: 'get' | 'post' | 'put' | 'delete', data?: P): Promise<unknown> {
      if (!endpoints.custom || !endpoints.custom[name]) {
        throw new Error(`custom endpoint "${name}" not configured`);
      }
      const endpointDef = endpoints.custom[name];
      const endpoint = typeof endpointDef === 'function'
        ? endpointDef(data)
        : endpointDef;

      switch (method) {
        case 'get':
          return get(endpoint);
        case 'post':
          return post(endpoint, (data ?? {}) as Record<string, unknown>);
        case 'put':
          return put(endpoint, (data ?? {}) as Record<string, unknown>);
        case 'delete':
          return del(endpoint);
        default:
          throw new Error(`Unknown HTTP method: ${method}`);
      }
    },

    /**
     * Batch operations
     */
    async batchCreate(items: U[]): Promise<T[]> {
      return Promise.all(items.map(item => this.create(item)));
    },

    async batchDelete(ids: ID[]): Promise<void> {
      return Promise.all(ids.map(id => this.delete(id))).then(() => undefined);
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
