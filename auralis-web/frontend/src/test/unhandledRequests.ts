/**
 * REST calls MSW had no handler for, collected during the running test (#5681).
 *
 * setup.ts fails the test in afterEach if any are left. A spec that deliberately drives requests
 * nothing answers (useRestAPI.test stubs global.fetch itself and asserts on the calls) clears the
 * list in its own afterEach, which runs before setup.ts's.
 */
export const unhandledApiRequests: string[] = [];
