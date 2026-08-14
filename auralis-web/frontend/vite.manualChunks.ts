/**
 * Rollup `manualChunks` rule for the production build.
 *
 * Lives in its own module so it can be unit-tested without importing
 * vite.config.mts (which drags esbuild into the jsdom test environment).
 * See src/__tests__/viteChunking.test.ts and #4697.
 *
 * Separate vendor chunk for better module initialization order.
 * Critical: this prevents 'Paper is not defined' errors in Electron/AppImage
 * by ensuring React, ReactDOM and MUI load before application code. That
 * failure mode reproduces ONLY in a packaged build — never in `vite dev` or
 * `vite preview` — so any change here must be verified against a packaged
 * AppImage.
 *
 * #4697 asked whether Redux Toolkit, @tanstack/react-query,
 * @tanstack/react-virtual and @hello-pangea/dnd should also be split out of
 * the eager `App` chunk. Measured and deliberately declined — do not "fix"
 * this by adding rules here without re-reading that issue. In short:
 *
 *   - Every large item left in `App` is a root-level provider that runs before
 *     first paint: DragDropContext (@hello-pangea/dnd, 185 kB rendered, the
 *     single biggest module in the chunk) wraps the whole tree in
 *     components/core/AppContainer.tsx, and the Redux and React Query
 *     providers wrap it too. Deferring any of them means swapping the element
 *     type at the root after mount, which remounts the entire app —
 *     unacceptable mid-playback.
 *   - Splitting them into *additional eager* chunks moves bytes between files
 *     without removing any startup work. Auralis is an Electron app served
 *     from localhost, so there is no download to parallelise — only the same
 *     parse cost, plus fresh exposure to the init-order failure above.
 *
 * Note the predicate is a substring match, so `node_modules/react` also
 * captures react-redux, react-dom and react-infinite-scroll-component. That is
 * harmless for the init-order guarantee (it only ever pulls *more* into the
 * earlier chunk) and narrowing it would move modules across the boundary for
 * no benefit.
 *
 * @param id Resolved module id
 * @returns Chunk name, or undefined to let Rollup decide
 */
export function vendorChunk(id: string): string | undefined {
  // Explicitly put vendor libraries in vendor chunk
  if (
    id.includes('node_modules/react') ||
    id.includes('node_modules/@mui') ||
    id.includes('node_modules/@emotion')
  ) {
    return 'vendor'
  }
  return undefined
}
