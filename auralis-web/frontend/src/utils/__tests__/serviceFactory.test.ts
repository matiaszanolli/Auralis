import { describe, it, expect, vi } from 'vitest';
import { createCrudService, createEndpointGenerator } from '../serviceFactory';

// Mock the apiRequest module
vi.mock('../apiRequest', () => ({
  get: vi.fn(async (url: string) => ({ url, method: 'GET' })),
  post: vi.fn(async (url: string, data: any) => ({ url, method: 'POST', data })),
  put: vi.fn(async (url: string, data: any) => ({ url, method: 'PUT', data })),
  del: vi.fn(async (url: string) => ({ url, method: 'DELETE' })),
}));

describe('serviceFactory', () => {
  describe('createCrudService', () => {
    it('list() should call string endpoint', async () => {
      const service = createCrudService({ list: '/api/items' });
      const result = await service.list();
      expect(result).toEqual({ url: '/api/items', method: 'GET' });
    });

    it('list() should call function endpoint with params', async () => {
      const service = createCrudService({ list: (p: any) => `/api/items?page=${p.page}` });
      const result = await service.list({ page: 2 });
      expect(result).toEqual({ url: '/api/items?page=2', method: 'GET' });
    });

    it('list() should throw if not configured', async () => {
      const service = createCrudService({});
      await expect(service.list()).rejects.toThrow('list endpoint not configured');
    });

    it('getOne() should call string endpoint', async () => {
      const service = createCrudService({ get: '/api/items/1' });
      const result = await service.getOne(1);
      expect(result).toEqual({ url: '/api/items/1', method: 'GET' });
    });

    it('getOne() should call function endpoint with id', async () => {
      const service = createCrudService({ get: (id: number) => `/api/items/${id}` });
      const result = await service.getOne(42);
      expect(result).toEqual({ url: '/api/items/42', method: 'GET' });
    });

    it('getOne() should throw if not configured', async () => {
      const service = createCrudService({});
      await expect(service.getOne(1)).rejects.toThrow('get endpoint not configured');
    });

    it('create() should post data to string endpoint', async () => {
      const service = createCrudService({ create: '/api/items' });
      const result = await service.create({ name: 'test' });
      expect(result).toEqual({ url: '/api/items', method: 'POST', data: { name: 'test' } });
    });

    it('create() should throw if not configured', async () => {
      const service = createCrudService({});
      await expect(service.create({})).rejects.toThrow('create endpoint not configured');
    });

    it('update() should put data to string endpoint', async () => {
      const service = createCrudService({ update: '/api/items/1' });
      const result = await service.update(1, { name: 'updated' });
      expect(result).toEqual({ url: '/api/items/1', method: 'PUT', data: { name: 'updated' } });
    });

    it('update() should throw if not configured', async () => {
      const service = createCrudService({});
      await expect(service.update(1, {})).rejects.toThrow('update endpoint not configured');
    });

    it('delete() should call string endpoint', async () => {
      const service = createCrudService({ delete: '/api/items/1' });
      const result = await service.delete(1);
      expect(result).toEqual({ url: '/api/items/1', method: 'DELETE' });
    });

    it('delete() should throw if not configured', async () => {
      const service = createCrudService({});
      await expect(service.delete(1)).rejects.toThrow('delete endpoint not configured');
    });

    it('custom() should route to correct HTTP method', async () => {
      const service = createCrudService({ custom: { archive: '/api/items/archive' } });

      expect(await service.custom('archive', 'get')).toEqual({ url: '/api/items/archive', method: 'GET' });
      expect(await service.custom('archive', 'post', { ids: [1] })).toEqual({
        url: '/api/items/archive', method: 'POST', data: { ids: [1] },
      });
      expect(await service.custom('archive', 'put', { ids: [1] })).toEqual({
        url: '/api/items/archive', method: 'PUT', data: { ids: [1] },
      });
      expect(await service.custom('archive', 'delete')).toEqual({ url: '/api/items/archive', method: 'DELETE' });
    });

    it('custom() should throw for unconfigured endpoint', async () => {
      const service = createCrudService({});
      await expect(service.custom('missing', 'get')).rejects.toThrow('custom endpoint "missing" not configured');
    });

    it('custom() should support function endpoints', async () => {
      const service = createCrudService({
        custom: { byTag: (tag: string) => `/api/items?tag=${tag}` },
      });
      const result = await service.custom('byTag', 'get', 'rock');
      expect(result).toEqual({ url: '/api/items?tag=rock', method: 'GET' });
    });
  });

  describe('createEndpointGenerator', () => {
    it('withId should append id to base URL', () => {
      const gen = createEndpointGenerator('/api/items');
      expect(gen.withId(42)).toBe('/api/items/42');
    });

    it('withParam should add single query param', () => {
      const gen = createEndpointGenerator('/api/items');
      expect(gen.withParam('page', 3)).toBe('/api/items?page=3');
    });

    it('withParams should add multiple query params', () => {
      const gen = createEndpointGenerator('/api/items');
      expect(gen.withParams({ page: 1, limit: 10 })).toBe('/api/items?page=1&limit=10');
    });

    it('withParams should return base URL for empty params', () => {
      const gen = createEndpointGenerator('/api/items');
      expect(gen.withParams({})).toBe('/api/items');
    });
  });
});
