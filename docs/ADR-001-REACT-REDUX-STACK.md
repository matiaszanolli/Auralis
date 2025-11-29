# ADR-001: React 18 + TypeScript + Redux Toolkit Stack

**Status**: Accepted
**Date**: 2024-11-28
**Author**: Architecture Team
**Decision**: Use React 18 with TypeScript, Redux Toolkit, and TanStack Query for frontend
**Applies To**: All new frontend code and gradual migration of existing code

---

## Context

The current Auralis frontend has accumulated technical debt:
- Monolithic components (500+ lines)
- Mixed concerns (UI + business logic)
- Manual state management without clear patterns
- Poor performance on slow networks
- Difficult to test and extend

The modernization initiative requires a modern, scalable frontend architecture that can support the Phase 7.5 caching improvements and future feature development.

### Requirements

1. **Type Safety**: Prevent runtime errors through compile-time checking
2. **State Management**: Predictable, debuggable state with Redux
3. **Server State**: Intelligent caching of API responses
4. **Performance**: < 1.5s FCP, < 2.5s LCP, 60 FPS animations
5. **Developer Experience**: Fast hot reload, good debugging tools
6. **Maintainability**: Clear separation of concerns, modular architecture
7. **Testing**: Easy to unit test, integration test, and E2E test

---

## Decision

Adopt the following frontend stack:

### Core Framework
- **React 18+** with TypeScript (strict mode)
- **Vite** for development (HMR, fast builds)
- **TypeScript strict mode** (noImplicitAny, noUnusedVariables, etc.)

### State Management
- **Redux Toolkit** for client state (player, queue, library)
- **Redux DevTools** for debugging
- **Thunk middleware** for async operations
- **Normalized state** structure for performance

### Server State
- **TanStack Query (React Query)** for API caching
- **Automatic stale-while-revalidate** patterns
- **Optimistic updates** with rollback on error
- **Integration with Phase 7.5 cache** for 10-500x speedup

### Build & Runtime
- **Vite** for development and production builds
- **esbuild** for fast transpilation
- **TypeScript** strict mode for type safety
- **Tree shaking** for minimal production bundle

### Testing
- **Vitest** for unit tests (Jest-compatible API, much faster)
- **React Testing Library** for component tests (behavior-driven)
- **Playwright** for E2E tests (cross-browser support)
- **MSW** for API mocking in tests
- **@testing-library/user-event** for realistic interactions

### Styling
- **Design tokens** from `src/design-system/tokens.ts` (single source of truth)
- **CSS-in-JS** (styled-components or Tailwind - decision pending)
- **No hardcoded colors or spacing** (always use tokens)

### Development Tools
- **VS Code** as standard IDE
- **ESLint** for code quality
- **Prettier** for code formatting
- **Lighthouse CI** for performance monitoring
- **React DevTools** and **Redux DevTools** browser extensions

---

## Rationale

### Why React 18?
- Industry standard for UI libraries
- Excellent ecosystem and community support
- Concurrent features for performance (automatic batching)
- Good TypeScript support
- Widely known by developers

### Why TypeScript?
- Catch errors at compile time, not runtime
- Excellent IDE support (autocomplete, refactoring)
- Self-documenting code (types as documentation)
- Easier refactoring with confidence
- Mandatory for large projects (reduces bugs by ~30%)

### Why Redux Toolkit?
- Predictable state management (single source of truth)
- Easy to debug (Redux DevTools time-travel)
- Clear action/reducer pattern
- Middleware support for side effects
- Better than: useState scattered everywhere, Context API (performance), Zustand (learning curve)

### Why TanStack Query?
- Intelligent API response caching
- Automatic stale-while-revalidate pattern
- Deduplication of identical requests
- Optimistic updates with rollback
- Reduces Redux for server state (Redux is for client state)
- Works seamlessly with Phase 7.5 backend cache

### Why Vite?
- 10-100x faster than webpack for development
- Instant hot module replacement (HMR)
- Fast production builds
- Better developer experience
- Modern tool (not legacy like CRA)

### Why Vitest?
- 5-10x faster than Jest (same API)
- Better TypeScript support
- Faster startup time
- Integrated with Vite
- Active development and community

---

## Architecture Overview

### Component Layers

```
┌─────────────────────────────────────────┐
│  Pages/Screens (Page.tsx)               │
│  - Orchestrate features                 │
│  - Connect to Redux/hooks               │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│  Container Components (Feature.tsx)     │
│  - Connect to Redux/hooks               │
│  - Handle data fetching (TanStack)      │
│  - Pass data to presentational          │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│  Presentational Components (<300 lines) │
│  - Pure (no side effects)               │
│  - Receive props only                   │
│  - Reusable across app                  │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│  Base Component Library                 │
│  - Button, Modal, Input, etc.           │
│  - Design system tokens                 │
│  - Reusable across features             │
└─────────────────────────────────────────┘
```

### State Structure

```typescript
interface AppState {
  player: {
    isPlaying: boolean;
    currentTrack: Track | null;
    position: number;
    volume: number;
    playbackRate: number;
  };
  queue: {
    tracks: Track[];
    position: number;
    history: Track[];
  };
  library: {
    selectedGenre: string | null;
    viewMode: 'grid' | 'list';
    sortBy: 'title' | 'artist' | 'dateAdded';
  };
  ui: {
    isLoading: boolean;
    error: Error | null;
    notifications: Notification[];
  };
}
```

### Directory Structure

```
src/
├── components/
│   ├── Player/
│   │   ├── PlayerControls.tsx
│   │   ├── ProgressBar.tsx
│   │   ├── VolumeControl.tsx
│   │   └── types.ts
│   ├── Queue/
│   │   ├── QueueDisplay.tsx
│   │   ├── VirtualizedQueue.tsx
│   │   └── types.ts
│   ├── Library/
│   │   ├── LibraryBrowser.tsx
│   │   ├── SearchBar.tsx
│   │   └── TrackGrid.tsx
│   └── Common/
│       ├── Button.tsx
│       ├── Modal.tsx
│       └── LoadingSpinner.tsx
├── features/
│   ├── player/
│   │   ├── playerSlice.ts    (Redux)
│   │   ├── playerSelectors.ts (Memoized selectors)
│   │   └── hooks.ts
│   ├── queue/
│   │   ├── queueSlice.ts
│   │   └── hooks.ts
│   └── library/
│       ├── librarySlice.ts
│       └── hooks.ts
├── hooks/
│   ├── usePlayer.ts
│   ├── useQueue.ts
│   ├── useWebSocket.ts
│   └── useKeyboardShortcuts.ts
├── services/
│   ├── api.ts          (Axios/fetch wrapper)
│   ├── websocket.ts    (WebSocket client)
│   └── cache.ts        (TanStack Query setup)
├── store/
│   ├── store.ts        (Redux store config)
│   └── middleware.ts   (Custom middleware)
├── design-system/
│   └── tokens.ts       (Colors, spacing, typography)
├── test/
│   ├── mocks/
│   │   └── handlers.ts (MSW mock handlers)
│   └── test-utils.ts   (Custom render, etc.)
└── App.tsx
```

---

## Implementation Approach

### Phase 1: Foundation (Week 1-2)
1. Setup Vite + TypeScript + Redux Toolkit
2. Create design system and base components
3. Setup testing infrastructure (Vitest, React Testing Library)
4. Create project structure and initial pages

### Phase 2: Core Components (Week 3-4)
1. Implement player controls (play/pause/skip)
2. Build queue display with virtual scrolling
3. Create library browser with search
4. Setup keyboard navigation and ARIA labels

### Phase 3: State & Integration (Week 5-6)
1. Implement Redux slices (player, queue, library)
2. Create custom hooks (usePlayer, useQueue, etc.)
3. Integrate TanStack Query for API caching
4. Implement WebSocket real-time updates

### Phase 4: Polish & Optimization (Week 7-9)
1. Performance optimization (memoization, code splitting, lazy loading)
2. Accessibility audit and fixes (WCAG AA)
3. Browser testing (Chrome, Firefox, Safari, Edge)
4. E2E tests with Playwright

---

## Consequences

### Positive
- ✅ Modern, maintainable codebase
- ✅ Type-safe development
- ✅ Excellent developer experience (HMR, debugging)
- ✅ 3-5x faster development iteration
- ✅ Better performance (bundler optimization, lazy loading)
- ✅ Easier testing (Vitest is fast)
- ✅ Scales to large teams
- ✅ Leverages Phase 7.5 cache improvements

### Trade-offs
- ⚠️ Learning curve for Redux + TanStack Query (2-3 days)
- ⚠️ Requires Node 16+, modern browser support
- ⚠️ Initial setup complexity (Vite config, ESLint, Prettier)
- ⚠️ Migration effort for existing code (~2-3 weeks gradual)

### Mitigations
- Provide clear documentation and examples
- Setup linters to enforce patterns
- Create code generation templates
- Pair programming for initial phase
- Comprehensive test coverage

---

## Metrics & Validation

### Success Criteria
- ✅ FCP < 1.5s (First Contentful Paint)
- ✅ LCP < 2.5s (Largest Contentful Paint)
- ✅ CLS < 0.1 (Cumulative Layout Shift)
- ✅ Bundle size < 500KB (gzipped)
- ✅ 85%+ test coverage
- ✅ Lighthouse > 90 score
- ✅ 60 FPS on scroll/animations

### Measurement Tools
- **Lighthouse CI** for performance monitoring
- **Bundlesize** for bundle size tracking
- **Coverage.py** for test coverage reporting
- **WebPageTest** for detailed performance analysis
- **Chrome DevTools** for profiling

---

## Related Decisions
- ADR-002: Phase 7.5 Cache Integration Approach
- ADR-003: WebSocket Message Protocol Design
- ADR-004: Component Size and Structure Limits

---

## References
- [React 18 Documentation](https://react.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Redux Toolkit Documentation](https://redux-toolkit.js.org/)
- [TanStack Query Documentation](https://tanstack.com/query/latest)
- [Vite Documentation](https://vitejs.dev/)
- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library Best Practices](https://testing-library.com/docs/react-testing-library/intro/)

---

**Next Review**: After Phase A completion (Week 2)
**Last Updated**: 2024-11-28
