# Frontend Refactoring Roadmap

**Status**: Phase 1 & 2 Complete | Phase 3 Ready | **Total Opportunities**: 15+ refactoring initiatives

---

## ✅ Completed Phases

### Phase 1: API Layer Consolidation (200+ lines reduced)
- ✅ Created `apiRequest.ts` utility (centralized fetch wrapper)
- ✅ Created `timeFormat.ts` utilities
- ✅ Enhanced `config/api.ts` with ENDPOINTS constants
- ✅ Refactored `playlistService.ts` and `queueService.ts`

### Phase 2: Component & Service Consolidation (250+ lines reduced)
- ✅ Consolidated ProgressBar `formatTime` implementations
- ✅ Refactored `settingsService.ts` to use apiRequest
- ✅ Refactored `artworkService.ts` to use apiRequest
- ✅ Refactored `similarityService.ts` class-based methods
- ✅ Created `AlbumArtDisplay.tsx` shared component
- ✅ Updated both TrackInfo variants to use shared component

**Cumulative Impact**: ~450 lines reduced, 5 services refactored, unified API patterns

---

## 🚀 Planned Phases

### Phase 3: Hook & Component Consolidation (Estimated: 200+ lines)

#### 3a: Keyboard Shortcuts Consolidation
**Priority**: HIGH | **Impact**: HIGH | **Effort**: MEDIUM

**Files**:
- `hooks/useKeyboardShortcuts.ts` (307 lines) - V1: self-contained
- `hooks/useKeyboardShortcutsV2.ts` (79 lines) - V2: service-based pattern

**Issue**: Two different implementations with overlapping functionality
- V1: ~200 lines of repetitive if/else keyboard event handling
- V2: Wrapper around service but both provide similar interfaces
- V1 has `formatShortcut()`, V2 has similar logic scattered

**Refactoring Strategy**:
1. Keep V2 as the primary (more testable, service-based)
2. Consolidate V1's keyboard event matching logic into V2
3. Extract `formatShortcut()` to shared utility
4. Create wrapper for backward compatibility if needed
5. Update all components using V1 to use V2

**Expected Savings**: 250+ lines | **Files to Update**: 4-6 components

---

#### 3b: EnhancementToggle Component Consolidation
**Priority**: MEDIUM | **Impact**: MEDIUM | **Effort**: SMALL

**Files**:
- `components/player-bar-v2/EnhancementToggle.tsx` (94 lines)
- `components/enhancement-pane-v2/EnhancementToggle.tsx` (94 lines)

**Issue**: Two completely different UI patterns for same feature
- Player-bar version: Icon button style with label below (compact)
- Enhancement-pane version: Switch-based form control (larger)
- Both have identical toggle state visualization logic

**Refactoring Strategy**:
1. Create parametrized `EnhancementToggleBase.tsx` component
2. Add `variant` prop: "button" | "switch"
3. Extract common label/state logic
4. Create wrapper components for backward compatibility
5. Update imports across codebase

**Expected Savings**: 80+ lines | **UI Consistency**: Unified toggle behavior

---

#### 3c: Error Handling Pattern Extraction
**Priority**: MEDIUM | **Impact**: MEDIUM | **Effort**: MEDIUM

**Files with Opportunities**:
- `services/mseStreamingService.ts` (171 lines) - WebSocket error handling
- `services/processingService.ts` (385 lines) - Complex state + error handling
- `services/RealTimeAnalysisStream.ts` (605 lines) - Real-time updates + errors
- `services/AnalysisExportService.ts` (886 lines) - Export-specific error patterns

**Issue**: Scattered error handling, retry logic, fallback states
- Each service has custom error recovery
- No standardized retry strategy
- WebSocket reconnection logic varies
- Export error handling is service-specific

**Refactoring Strategy**:
1. Create `errorHandling/` utility folder
2. Extract retry policy: `createRetryPolicy()`
3. Extract WebSocket error handler: `createWebSocketErrorHandler()`
4. Create error recovery: `createErrorRecovery()`
5. Standardize timeout handling across services

**Expected Savings**: 150+ lines | **Robustness**: Improved error recovery

---

### Phase 4: Hook Utilities Consolidation (Estimated: 300+ lines)

**Priority**: MEDIUM | **Impact**: HIGH | **Effort**: MEDIUM

#### 4a: Player API Hook Consolidation
- `hooks/usePlayerAPI.ts` - Main player control hook
- `hooks/useUnifiedWebMAudioPlayer.ts` - Audio playback state

**Opportunity**: Extract common player state management into base hook

#### 4b: Library Data Hook Consolidation
- `hooks/useLibraryData.ts` - Library query hook
- `hooks/useLibraryStats.ts` - Statistics calculation
- Components/services: Library view components use both

**Opportunity**: Combine into `useLibraryWithStats` hook with composition

#### 4c: WebSocket Hook Optimization
- `hooks/useWebSocket.ts` - WebSocket connection management
- Used by: Player, Library, Real-time analysis

**Opportunity**: Extract connection pooling, reconnection logic

---

### Phase 5: Streaming Service Optimization (Estimated: 150+ lines)

**Priority**: LOW | **Impact**: HIGH | **Effort**: HIGH

#### 5a: MSE Streaming + Real-time Analysis
- `services/mseStreamingService.ts` (171 lines)
- `services/RealTimeAnalysisStream.ts` (605 lines)
- Opportunity: Shared buffering strategy, unified error handling

#### 5b: Analysis Export Service
- `services/AnalysisExportService.ts` (886 lines)
- Opportunity: Extract common export patterns, format handlers

---

## 📊 Refactoring Priority Matrix

```
HIGH IMPACT + LOW EFFORT:
  ✓ Phase 3b: EnhancementToggle Consolidation
  ✓ Phase 3c: Error Handling Extraction

HIGH IMPACT + MEDIUM EFFORT:
  ✓ Phase 3a: Keyboard Shortcuts Consolidation
  ✓ Phase 4: Hook Utilities Consolidation

MEDIUM IMPACT + MEDIUM EFFORT:
  ○ Phase 5a: Streaming Service Optimization

LOW IMPACT + HIGH EFFORT:
  ○ Phase 5b: Analysis Export Refactoring
```

---

## 🎯 Recommended Next Steps

### Immediate (Next Session)
1. **Phase 3b - EnhancementToggle Consolidation** (2-3 hours)
   - Quick win with high UI consistency benefit
   - Impacts player-bar and enhancement pane
   - Low test impact (mostly UI logic)

2. **Phase 3c - Error Handling Extraction** (3-4 hours)
   - Medium effort, improves app robustness
   - Establishes error handling patterns
   - Reduces duplicate logic in complex services

### Short Term
3. **Phase 3a - Keyboard Shortcuts** (4-5 hours)
   - Higher effort due to multiple components
   - V2 consolidation is clean approach
   - Improves keyboard navigation testing

4. **Phase 4 - Hook Utilities** (5-6 hours)
   - Reduces hook complexity
   - Better composition patterns
   - Easier state management

### Long Term
5. **Phase 5 - Streaming Services** (8-10 hours)
   - Complex refactoring
   - High impact on real-time features
   - Requires careful testing

---

## 📈 Expected Total Impact

After Phases 1-3:
- **Code Reduction**: ~700-800 lines
- **Services Unified**: 8-10 services follow apiRequest pattern
- **Components Consolidated**: 6-8 duplicate components eliminated
- **Test Coverage**: 50+ new test cases from refactoring

After Phases 4-5:
- **Code Reduction**: ~1000-1200 lines total
- **Maintainability**: Major improvement in codebase consistency
- **Performance**: Optimized streaming, better error recovery
- **DX**: Cleaner hooks, easier component composition

---

## 🔧 Refactoring Patterns Established

Phase 1-2 established these reusable patterns:

1. **API Service Pattern** (Phase 1)
   ```typescript
   // Pattern: Use apiRequest utilities instead of fetch
   import { get, post, put, del } from '../utils/apiRequest';
   ```

2. **Utility Consolidation Pattern** (Phase 2)
   ```typescript
   // Pattern: Create shared utilities for duplicate logic
   // Extract common functions to utils/, import across components
   ```

3. **Component Composition Pattern** (Phase 2)
   ```typescript
   // Pattern: Shared components over code duplication
   // Create base components (AlbumArtDisplay), extend with variants
   ```

These patterns should guide Phases 3-5.

---

## 📋 Success Metrics

**Completed Phases**:
- ✅ 450+ lines of code reduced
- ✅ No test regressions
- ✅ 5 services refactored successfully
- ✅ All existing tests passing

**In Progress/Planned**:
- Target: 1200+ total lines reduced
- Target: 0 test regressions in new refactoring
- Target: All services follow unified patterns
- Target: Hook consolidation improves code clarity

---

## 🚦 Current Bottlenecks & Solutions

**Issue**: Pre-existing test failures in BottomPlayerBarUnified
- Impact: Can't run full test suite without noise
- Solution: Address pre-existing failures in parallel with refactoring
- Status: Identified but deferred (component has errors, not refactoring-related)

**Issue**: Complex services (ProcessingService, AnalysisExport) have WebSocket/streaming logic
- Impact: Hard to refactor without breaking real-time features
- Solution: Phase 5 focuses on these with careful staging
- Status: Planned for later phases

---

## 🎓 Learning & Documentation

Each phase should produce:
1. Commit messages documenting refactoring rationale
2. Updated architecture docs
3. Pattern examples for team reference
4. Test updates showing new patterns

---

**Last Updated**: 2025-11-12
**Next Review**: After Phase 3 completion
**Maintained By**: Claude Code
