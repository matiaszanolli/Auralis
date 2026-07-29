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

describe('createCrudService — request cancellation (#4614)', () => {
  // The factory generated methods that called get/post/put/del with no
  // options object, so all five factory-built services (playlistService,
  // queueService, settingsService, similarityService, artworkService) were
  // structurally unable to abort an in-flight request — the only HTTP layer
  // in the codebase excluded from the cancellation discipline.

  const mocked = async () => await import('../apiRequest');

  it('list() forwards the signal', async () => {
    const { get } = await mocked();
    vi.mocked(get).mockClear();
    const controller = new AbortController();
    const service = createCrudService({ list: '/api/items' });

    await service.list(undefined, { signal: controller.signal });

    expect(get).toHaveBeenCalledWith('/api/items', { signal: controller.signal });
  });

  it('getOne() forwards the signal', async () => {
    const { get } = await mocked();
    vi.mocked(get).mockClear();
    const controller = new AbortController();
    const service = createCrudService({ get: '/api/items/1' });

    await service.getOne(1, { signal: controller.signal });

    expect(get).toHaveBeenCalledWith('/api/items/1', { signal: controller.signal });
  });

  it('create() forwards the signal', async () => {
    const { post } = await mocked();
    vi.mocked(post).mockClear();
    const controller = new AbortController();
    const service = createCrudService({ create: '/api/items' });

    await service.create({ a: 1 }, { signal: controller.signal });

    expect(post).toHaveBeenCalledWith('/api/items', { a: 1 }, { signal: controller.signal });
  });

  it('update() forwards the signal', async () => {
    const { put } = await mocked();
    vi.mocked(put).mockClear();
    const controller = new AbortController();
    const service = createCrudService({ update: (id: number) => `/api/items/${id}` });

    await service.update(7, { a: 1 }, { signal: controller.signal });

    expect(put).toHaveBeenCalledWith('/api/items/7', { a: 1 }, { signal: controller.signal });
  });

  it('delete() forwards the signal', async () => {
    const { del } = await mocked();
    vi.mocked(del).mockClear();
    const controller = new AbortController();
    const service = createCrudService({ delete: (id: number) => `/api/items/${id}` });

    await service.delete(7, { signal: controller.signal });

    expect(del).toHaveBeenCalledWith('/api/items/7', { signal: controller.signal });
  });

  it('custom() forwards the signal for every method', async () => {
    const { get, post, put, del } = await mocked();
    const controller = new AbortController();
    const service = createCrudService({ custom: { act: '/api/items/act' } });

    for (const fn of [get, post, put, del]) vi.mocked(fn).mockClear();

    await service.custom('act', 'get', undefined, { signal: controller.signal });
    await service.custom('act', 'post', undefined, { signal: controller.signal });
    await service.custom('act', 'put', undefined, { signal: controller.signal });
    await service.custom('act', 'delete', undefined, { signal: controller.signal });

    expect(get).toHaveBeenCalledWith('/api/items/act', { signal: controller.signal });
    expect(post).toHaveBeenCalledWith('/api/items/act', {}, { signal: controller.signal });
    expect(put).toHaveBeenCalledWith('/api/items/act', {}, { signal: controller.signal });
    expect(del).toHaveBeenCalledWith('/api/items/act', { signal: controller.signal });
  });

  it('batch operations forward the signal to every request', async () => {
    const { post, del } = await mocked();
    const controller = new AbortController();
    const service = createCrudService({
      create: '/api/items',
      delete: (id: number) => `/api/items/${id}`,
    });

    vi.mocked(post).mockClear();
    vi.mocked(del).mockClear();

    await service.batchCreate([{ a: 1 }, { a: 2 }], { signal: controller.signal });
    await service.batchDelete([1, 2], { signal: controller.signal });

    expect(post).toHaveBeenCalledTimes(2);
    expect(del).toHaveBeenCalledTimes(2);
    for (const call of vi.mocked(post).mock.calls) {
      expect(call[2]).toEqual({ signal: controller.signal });
    }
    for (const call of vi.mocked(del).mock.calls) {
      expect(call[1]).toEqual({ signal: controller.signal });
    }
  });

  it('passes no options object when neither a guard nor a signal is given', async () => {
    // #4607 established that services without a guard keep the exact previous
    // call signature. #4614 must not disturb that.
    const { get, post, put, del } = await mocked();
    for (const fn of [get, post, put, del]) vi.mocked(fn).mockClear();

    const service = createCrudService({
      list: '/api/items',
      get: '/api/items/1',
      create: '/api/items',
      update: '/api/items/1',
      delete: '/api/items/1',
    });

    await service.list();
    await service.getOne(1);
    await service.create({ a: 1 });
    await service.update(1, { a: 1 });
    await service.delete(1);

    // Exact arity, not a trailing `undefined` — playlistService's existing
    // tests assert `toHaveBeenCalledWith(url)` and must keep passing.
    expect(get).toHaveBeenNthCalledWith(1, '/api/items');
    expect(get).toHaveBeenNthCalledWith(2, '/api/items/1');
    expect(post).toHaveBeenCalledWith('/api/items', { a: 1 });
    expect(put).toHaveBeenCalledWith('/api/items/1', { a: 1 });
    expect(del).toHaveBeenCalledWith('/api/items/1');
  });

  it('omits the options argument entirely when there is nothing to pass', () => {
    // Pins the arity itself: an explicit trailing `undefined` would satisfy
    // toHaveBeenCalledWith(url, undefined) but break existing service tests.
    const service = createCrudService({ list: '/api/items' });
    return (async () => {
      const { get } = await mocked();
      vi.mocked(get).mockClear();
      await service.list();
      expect(vi.mocked(get).mock.calls[0]).toHaveLength(1);
    })();
  });

  it('merges a configured guard with a caller signal rather than dropping either', async () => {
    const { get } = await mocked();
    vi.mocked(get).mockClear();
    const controller = new AbortController();
    const guard = (v: unknown) => Array.isArray(v);
    const service = createCrudService({ list: '/api/items', guards: { list: guard } });

    await service.list(undefined, { signal: controller.signal });

    expect(get).toHaveBeenCalledWith('/api/items', {
      signal: controller.signal,
      validate: guard,
    });
  });

  it('cannot be used to override a configured guard', async () => {
    // CrudRequestOptions is narrowed to `signal` precisely so a caller cannot
    // pass `validate` and defeat the #4607 shape checks.
    const { get } = await mocked();
    vi.mocked(get).mockClear();
    const guard = (v: unknown) => Array.isArray(v);
    const service = createCrudService({ list: '/api/items', guards: { list: guard } });

    await service.list(undefined, { validate: () => true } as never);

    expect(vi.mocked(get).mock.calls[0][1]).toEqual({ validate: guard });
  });
});
