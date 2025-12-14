# Phase 2 Enhancement Components Test Roadmap

**Status**: Phase 1 ✅ Complete | Phase 2 Library ✅ Complete | Phase 2 Enhancement 🚀 In Progress
**Target Coverage**: 55%+ overall test coverage
**Current Library Coverage**: 86 tests across 12 components (Phase 2 Library)

---

## Overview

Phase 2 Enhancement focuses on testing audio DSP parameter display and control components. This differs from Phase 1 (which tested data display and selection) by emphasizing **audio attribute change verification** rather than UI-only testing.

### Key Principle: Audio Attribute Testing (Not Presets)

Per user feedback: *"We don't have presets yet. We want to test that changes in every attribute of the music are well being applied."*

This means tests should verify:
- How component displays reflect actual DSP parameter values
- How parameter changes (loudness, EQ, compression, etc.) propagate through the UI
- Real-time polling and state synchronization with the backend
- Audio characteristic calculations and visualization

---

## Phase 2 Enhancement: 8 Components (Planned: 150+ tests)

### Component Group A: Parameter Display (60 tests)

#### 1. EnhancementPaneV2 (30 tests)
**Location**: `auralis-web/frontend/src/components/enhancement-pane-v2/EnhancementPaneV2.tsx`
**Purpose**: Main enhancement control hub - real-time parameter polling, display, and toggle

**Audio Attributes Tested**:
- Loudness target: -14 to -23 LUFS (main standard is -14 LUFS for streaming)
- Peak target: -1 to -6 dB (intersection point where loudness limiter triggers)
- Bass boost: 0 to 8 dB (low-frequency enhancement)
- Air/Treble boost: 0 to 6 dB (high-frequency enhancement)
- Compression ratio: 0 to 15% (dynamic range reduction)
- Expansion ratio: 0 to 2% (quiet section enhancement)
- Stereo width: 0 to 150% (spatial processing, 100% = mono)

**Test Categories**:

**Rendering & Display (8 tests)**
```
- Should render enhancement pane with all parameter displays
- Should show current loudness target (-14 LUFS by default)
- Should display peak target (-3 dB by default)
- Should show all EQ parameters (bass, air)
- Should display dynamics (compression, expansion)
- Should show stereo width percentage
- Should render parameter labels with correct units (LUFS, dB, %)
- Should conditionally show parameters when active (bass_boost > 0, etc.)
```

**Parameter Polling & Real-Time Updates (8 tests)**
```
- Should poll backend API every 2 seconds for parameter updates
- Should display updated loudness when backend value changes (-14 → -18)
- Should update EQ display when bass_boost changes (0 → 2.5)
- Should reflect compression changes (0 → 3)
- Should update stereo width in real-time (100 → 120)
- Should handle polling errors gracefully (retry or show offline state)
- Should stop polling when enhancement is disabled
- Should batch multiple parameter updates in single poll response
```

**State Transitions (6 tests)**
```
- Should disable all parameters when enhancement is toggled off
- Should re-enable parameters when enhancement is toggled on
- Should update display when switching between processing modes (adaptive/reference)
- Should show loading state during parameter fetch
- Should clear parameters when track changes
- Should preserve parameter state across re-renders
```

**Edge Cases & Error Handling (8 tests)**
```
- Should handle null/undefined parameters gracefully
- Should display extreme values (-23 LUFS, 8 dB bass boost, 150% stereo width)
- Should handle parameter API timeouts (show previous values)
- Should validate parameter ranges (clamp to min/max)
- Should handle rapid parameter updates (debounce or queue)
- Should recover from partial API response (some params missing)
- Should show "No track loaded" when parameters unavailable
- Should handle background API failures without crashing
```

**Accessibility (5 tests)**
```
- Should have proper ARIA labels for all parameters
- Should announce parameter changes to screen readers
- Should be keyboard navigable (Tab through parameters)
- Should have semantic HTML structure
- Should support high contrast mode
```

#### 2. ProcessingParameters Component (20 tests)
**Location**: `auralis-web/frontend/src/components/enhancement-pane-v2/ProcessingParameters.tsx`
**Purpose**: Display DSP parameter values with color-coded visualization

**Test Categories**:

**Parameter Display (12 tests)**
```
- Should display loudness target with LUFS unit (-14, -18, -23)
- Should show peak target in dB (-1, -3, -6)
- Should display bass boost in dB (0, 2.5, 5, 8)
- Should show air/treble boost in dB (0, 1.8, 4, 6)
- Should display compression percentage (0, 3, 6, 12, 15)
- Should show expansion percentage (0, 0.5, 1, 2)
- Should display stereo width as percentage (100, 105, 120, 150)
- Should show multiple parameters together (all DSP settings visible)
- Should conditionally hide zero values (don't show "bass boost: 0 dB")
- Should format decimal values correctly (2.5 dB not 2.50 or 2.500)
- Should right-align numeric values for readability
- Should update display when props change
```

**Color-Coded Visualization (5 tests)**
```
- Should use green for subtle processing (bass_boost < 1.5 dB)
- Should use amber/yellow for moderate processing (1.5 ≤ bass_boost ≤ 4 dB)
- Should use orange/red for aggressive processing (bass_boost > 4 dB)
- Should apply same color logic to all parameters (air_boost, compression, etc.)
- Should match Aurora color theme tokens
```

**Edge Cases (3 tests)**
```
- Should handle null parameters without rendering
- Should display extreme values correctly
- Should maintain formatting with very long parameter lists
```

#### 3. AudioCharacteristics Component (10 tests)
**Location**: `auralis-web/frontend/src/components/enhancement-pane-v2/AudioCharacteristics.tsx`
**Purpose**: 3D audio space visualization of spectral, dynamic, and energy characteristics

**Audio Metrics Tested** (all normalized 0-1):
- Spectral balance: 0 (dark/bass-heavy) to 1 (bright/treble-heavy)
- Dynamic range: 0 (compressed) to 1 (dynamic)
- Energy level: 0 (quiet) to 1 (loud)

**Test Categories**:

**Visualization Rendering (5 tests)**
```
- Should render 3D audio space visualization
- Should display spectral balance position (0, 0.5, 1)
- Should show dynamic range on separate axis (0, 0.5, 1)
- Should display energy level indicator (0, 0.5, 1)
- Should update visualization when characteristics change
```

**Characteristic Calculation (3 tests)**
```
- Should derive spectral balance from EQ parameters (high bass → low value)
- Should calculate dynamic range from compression/expansion
- Should compute energy level from loudness target
```

**Edge Cases (2 tests)**
```
- Should handle missing characteristics data
- Should display extreme characteristic values (0 and 1)
```

### Component Group B: Control & Settings (50 tests)

#### 4. ParameterBar Component (15 tests)
**Location**: `auralis-web/frontend/src/components/enhancement-pane-v2/ParameterBar.tsx`
**Purpose**: Individual parameter progress bar (handles 0-1 normalized values)

**Test Categories**:

**Rendering (5 tests)**
```
- Should render progress bar for parameter value
- Should display parameter label and value
- Should fill bar proportional to value (0.5 = 50% filled)
- Should show min/max bounds on bar
- Should update color based on parameter intensity
```

**Value Mapping (4 tests)**
```
- Should map normalized 0-1 values to visual width correctly
- Should display actual parameter value (in original units) while bar shows normalized
- Should handle parameter ranges (loudness -14 to -23, EQ 0 to 8 dB)
- Should show correct units in label (LUFS, dB, %)
```

**Interaction (4 tests)**
```
- Should allow click to adjust value (optional interactive bar)
- Should prevent adjustment when enhancement disabled
- Should show tooltip on hover with exact value
- Should debounce rapid value changes
```

**Edge Cases (2 tests)**
```
- Should handle extreme values gracefully
- Should render without crashing when parameter data missing
```

#### 5. EnhancementToggle Components (20 tests - both versions)
**Location**:
- `auralis-web/frontend/src/components/enhancement-pane-v2/EnhancementToggle.tsx`
- `auralis-web/frontend/src/components/player-bar-v2/EnhancementToggle.tsx`

**Purpose**: Enable/disable enhancement processing switch

**Test Categories**:

**Toggle State (6 tests)**
```
- Should display enabled state (toggle ON)
- Should display disabled state (toggle OFF)
- Should toggle on click/tap
- Should call onToggle callback when clicked
- Should show loading state while toggling
- Should revert toggle if backend fails
```

**Visual Feedback (4 tests)**
```
- Should change color on toggle (green when ON, gray when OFF)
- Should show animated transition
- Should display tooltip showing current state
- Should have distinct visual states in both light and dark theme
```

**Accessibility (4 tests)**
```
- Should render as accessible switch element (role="switch")
- Should announce state to screen readers ("Enhancement processing on/off")
- Should be keyboard accessible (Space/Enter to toggle)
- Should have proper ARIA attributes (aria-checked, aria-label)
```

**Integration (6 tests)**
```
- Should disable all parameters when toggled OFF
- Should re-enable parameters when toggled ON
- Should sync with backend toggle state (poll and reflect changes)
- Should handle rapid toggle clicks (debounce)
- Should preserve toggle state across page reload
- Should work independently in both locations (pane + player bar)
```

#### 6. VolumeControl Component (10 tests)
**Location**: `auralis-web/frontend/src/components/enhancement-pane-v2/VolumeControl.tsx` or `player-bar-v2/`
**Purpose**: Volume slider (0.0 to 1.0 linear gain)

**Test Categories**:

**Slider Interaction (5 tests)**
```
- Should render volume slider (0-100%)
- Should drag slider to change volume (25%, 50%, 75%)
- Should click on track to seek to position
- Should show current volume value tooltip
- Should update on keyboard arrow keys (for accessibility)
```

**State Management (3 tests)**
```
- Should persist volume setting across track changes
- Should apply volume gain to audio output
- Should update when volume changed externally (other window, device)
```

**Edge Cases (2 tests)**
```
- Should handle mute button (toggle volume 0/previous)
- Should handle extreme volume levels gracefully
```

#### 7. SettingsDialog Component (15 tests)
**Location**: `auralis-web/frontend/src/components/enhancement-pane-v2/SettingsDialog.tsx`
**Purpose**: Enhancement intensity slider, preset selection, audio hardware settings

**Note**: This component tests *controls* not presets themselves (presets don't exist yet)

**Test Categories**:

**Enhancement Intensity Slider (5 tests)**
```
- Should render intensity slider (0-100%)
- Should map intensity to parameter amount (0% = no boost, 100% = max boost)
- Should scale bass_boost 0 to 8 dB with intensity
- Should scale air_boost 0 to 6 dB with intensity
- Should update DSP processing when intensity changes
```

**Dialog Interactions (5 tests)**
```
- Should open settings dialog on button click
- Should close dialog on save or cancel
- Should show current settings values
- Should apply changes immediately or on save (depends on implementation)
- Should persist settings across sessions
```

**Audio Hardware Settings (3 tests)**
```
- Should list available audio outputs (speakers, headphones, etc.)
- Should switch audio output on selection
- Should show current active output
```

**Accessibility (2 tests)**
```
- Should have proper dialog semantics (role="dialog")
- Should focus trap within dialog and return focus on close
```

### Component Group C: Data Flow & Real-Time Sync (40 tests)

#### 8. Integration Tests: Real-Time Parameter Updates
**Purpose**: Test how parameter changes flow through the entire enhancement UI

**Test Categories**:

**Backend to UI Sync (15 tests)**
```
- Should poll backend parameters every 2 seconds
- Should update EnhancementPaneV2 when loudness_target changes on backend
- Should refresh all parameter displays on single API call
- Should handle polling with empty response (keep displaying previous values)
- Should show error state if polling fails (network/timeout)
- Should retry polling after transient network error
- Should stop polling when component unmounts
- Should resume polling when component remounts
- Should handle rapid sequential parameter updates
- Should batch updates in single re-render
- Should detect when backend parameters differ from UI values
- Should sync UI back to backend if out of sync
- Should show "Syncing..." state during parameter updates
- Should timeout and show error after 5s with no response
- Should handle concurrent parameter changes from different sources
```

**Parameter Change Propagation (15 tests)**
```
- Should reflect user slider change → backend → back to UI within 2.5s
- Should update ProcessingParameters when loudness changes
- Should update AudioCharacteristics when EQ parameters change
- Should recalculate spectral balance when bass_boost increases
- Should update dynamic range display when compression changes
- Should change ParameterBar colors when intensity changes
- Should show toast notification for significant changes (bass_boost > 3 dB)
- Should handle parameter validation (clamp to min/max before displaying)
- Should show before/after values when parameter changes
- Should animate parameter value changes (smooth transition not instant jump)
- Should track parameter change history (show previous value in tooltip)
- Should prevent UI flicker during updates (use React keys correctly)
- Should handle out-of-order updates (newer update arrives after older one)
- Should merge parameter updates correctly (multiple params changing)
- Should handle parameter units conversion if needed (dB to linear, etc.)
```

**Error Handling & Recovery (10 tests)**
```
- Should handle API returning invalid parameter values
- Should show "Offline" indicator when polling stops
- Should queue parameter changes when offline, sync when online
- Should handle mixing old/new parameter formats
- Should fallback to default values if backend unavailable
- Should show which parameters are out of sync
- Should allow manual refresh of parameters (Refresh button)
- Should handle 429 rate limit (back off polling)
- Should handle 500 server error (show user-friendly message)
- Should handle parameter conflicts (user changed value while polling)
```

---

## Phase 3: Service & Hook Tests (Planned: 80+ tests)

### Critical Infrastructure Tests

#### 1. useAudioAttributes Hook (20 tests)
**Purpose**: Get current audio characteristics from real-time processing

**Tests**:
```
- Should return current loudness target from enhancement context
- Should return EQ parameters (bass_boost, air_boost)
- Should return dynamics parameters (compression, expansion)
- Should return stereo width
- Should calculate spectral balance from EQ params
- Should derive dynamic range from compression
- Should compute energy level from loudness
- Should update when track changes
- Should refresh on demand (useCallback return new values)
- Should return null when no track playing
- Should handle enhancement disabled (return default values)
- Should cache results to prevent unnecessary recalculations
- Should debounce rapid parameter changes
- Should support custom update interval
- Should clean up listeners on unmount
- Should handle hook errors gracefully
- Should work with different audio formats
- Should support offline mode
- Should integrate with EnhancementContext correctly
- Should provide TypeScript types for all attributes
```

#### 2. AudioProcessingService (20 tests)
**Purpose**: Backend communication for parameter changes and real-time updates

**Tests**:
```
- Should fetch current parameters from /api/enhancement/parameters
- Should apply parameter changes to /api/enhancement/apply endpoint
- Should poll parameters at configurable interval (2s default)
- Should batch multiple parameter changes
- Should validate parameter ranges before sending
- Should handle network timeouts (5s default)
- Should retry failed requests with exponential backoff
- Should cache responses to reduce API load
- Should emit events on parameter changes
- Should sync UI-initiated changes to backend
- Should detect conflicts between UI and backend changes
- Should handle 404 when enhancement API missing
- Should work with different API versions
- Should support authentication token refresh
- Should clean up polling on service destroy
- Should log parameter change history
- Should provide request/response telemetry
- Should handle streaming audio special cases
- Should support both REST and WebSocket backends
- Should provide type-safe API methods
```

#### 3. EnhancementContext & State Management (20 tests)
**Purpose**: Centralized parameter state and change propagation

**Tests**:
```
- Should initialize with default parameters
- Should update parameters from API polling
- Should notify all subscribed components on change
- Should prevent duplicate updates (referential equality)
- Should track parameter change history
- Should provide undo/redo capabilities
- Should serialize/deserialize state to localStorage
- Should handle context consumer unmount gracefully
- Should warn on memory leaks (multiple listeners)
- Should support parameter reset to defaults
- Should merge partial parameter updates
- Should validate state before updates
- Should provide isLoading indicator during sync
- Should track last successful sync timestamp
- Should support offline mode (queue changes)
- Should integrate with error boundary
- Should provide dev tools support
- Should optimize re-renders with useMemo
- Should handle rapid context consumer mounting/unmounting
- Should provide clear documentation with examples
```

#### 4. Parameter Validation & Clamping (10 tests)
**Purpose**: Ensure all parameters stay within valid ranges

**Tests**:
```
- Should clamp loudness_target to -23 to -14 LUFS
- Should clamp peak_target to -6 to -0.5 dB
- Should clamp bass_boost to 0 to 8 dB
- Should clamp air_boost to 0 to 6 dB
- Should clamp compression to 0 to 15%
- Should clamp expansion to 0 to 2%
- Should clamp stereo_width to 0 to 150%
- Should reject negative loudness values (replace with abs value)
- Should warn on out-of-range values
- Should handle invalid parameter types (string instead of number)
```

#### 5. Audio Attribute Calculation Service (10 tests)
**Purpose**: Compute derived audio characteristics from DSP parameters

**Tests**:
```
- Should calculate spectral balance: low bass_boost → 0, high air_boost → 1
- Should derive dynamic range: high compression → low value, expansion → higher
- Should compute energy level from loudness (normalized -23 to -14)
- Should handle missing parameters (return 0.5 as neutral)
- Should cache calculations with parameter input hash
- Should provide confidence scores (0-1) for each calculation
- Should support custom weighting for parameters
- Should handle edge cases (all params at max, all at min)
- Should match audio analysis fingerprint system weights
- Should document calculation formulas in code comments
```

---

## Test Infrastructure & Utilities

### Mock Services & Fixtures

```typescript
// Mock EnhancementAPI for consistent backend responses
mockEnhancementAPI = {
  getParameters: vi.fn().mockResolvedValue({
    loudness_target: -14,
    peak_target: -3,
    bass_boost: 0,
    air_boost: 0,
    compression: 0,
    expansion: 0,
    stereo_width: 100,
  }),
  applyParameters: vi.fn().mockResolvedValue({ success: true }),
}

// Mock EnhancementContext hook
mockEnhancementContext = {
  isEnabled: true,
  loudness_target: -14,
  peak_target: -3,
  bass_boost: 0,
  air_boost: 0,
  compression: 0,
  expansion: 0,
  stereo_width: 100,
  updateParameter: vi.fn(),
  toggleEnhancement: vi.fn(),
}

// Test fixture: Audio parameters covering all ranges
testParameterSets = {
  defaults: { loudness: -14, bass: 0, air: 0, comp: 0, exp: 0, width: 100 },
  subtle: { loudness: -14, bass: 1, air: 0.5, comp: 1, exp: 0.2, width: 105 },
  moderate: { loudness: -16, bass: 3, air: 2, comp: 3, exp: 0.5, width: 110 },
  aggressive: { loudness: -18, bass: 6, air: 4, comp: 8, exp: 1.5, width: 120 },
  extreme: { loudness: -23, bass: 8, air: 6, comp: 15, exp: 2, width: 150 },
}
```

### Test Utilities

```typescript
// Wait for parameter to change within timeout
async waitForParameterChange(
  container: HTMLElement,
  paramName: string,
  expectedValue: number,
  timeout: number = 2500
): Promise<void>

// Extract displayed parameter value from component
getDisplayedParameter(container: HTMLElement, paramName: string): number | null

// Simulate backend parameter change
simulateBackendParameterUpdate(newParams: Partial<Parameters>): void

// Check if parameters are visually highlighted (color change)
getParameterHighlightColor(container: HTMLElement, paramName: string): string

// Verify parameter display formatting
expectParameterFormatted(container: HTMLElement, value: number, unit: string): void
```

---

## Implementation Timeline

### Week 1: Parameter Display (Components 1-3)
- **EnhancementPaneV2**: 30 tests (polling, real-time updates)
- **ProcessingParameters**: 20 tests (display & formatting)
- **AudioCharacteristics**: 10 tests (visualization)

**Estimated Tests**: 60 tests
**Estimated Time**: 8-10 hours
**Coverage Target**: +5-7% overall

### Week 2: Controls & Settings (Components 4-7)
- **ParameterBar**: 15 tests
- **EnhancementToggle**: 20 tests (both versions)
- **VolumeControl**: 10 tests
- **SettingsDialog**: 15 tests

**Estimated Tests**: 60 tests
**Estimated Time**: 8-10 hours
**Coverage Target**: +5-7% overall

### Week 3: Real-Time Sync (Component 8)
- **Integration Tests**: 40 tests (data flow, polling, sync)

**Estimated Tests**: 40 tests
**Estimated Time**: 6-8 hours
**Coverage Target**: +3-5% overall

**Phase 2 Total**: 150+ tests, 15-25% coverage gain → **Estimated 35-40% overall**

### Phase 3: Services & Hooks (Weeks 4-5)
- **useAudioAttributes Hook**: 20 tests
- **AudioProcessingService**: 20 tests
- **EnhancementContext**: 20 tests
- **Parameter Validation**: 10 tests
- **Audio Attribute Calculation**: 10 tests

**Estimated Tests**: 80+ tests
**Estimated Time**: 12-15 hours
**Coverage Target**: +10-15% overall

**Phase 3 Total**: 80+ tests → **Estimated 45-55% overall**

---

## Key Testing Patterns for Audio Attributes

### Pattern 1: Parameter Change Verification

```typescript
describe('Parameter Change Propagation', () => {
  it('should update display when loudness_target changes from backend', async () => {
    // Render component
    const { rerender } = render(<EnhancementPaneV2 />)

    // Verify initial value displayed
    expect(screen.getByText(/-14/)).toBeInTheDocument() // -14 LUFS

    // Simulate backend parameter update
    simulateBackendParameterUpdate({ loudness_target: -18 })

    // Wait for polling interval + render
    await waitFor(() => {
      expect(screen.getByText(/-18/)).toBeInTheDocument()
    }, { timeout: 2500 })

    // Verify other parameters unchanged
    expect(screen.getByText(/-3/)).toBeInTheDocument() // peak_target still -3
  })
})
```

### Pattern 2: Audio Characteristic Calculation

```typescript
describe('Audio Characteristics Derivation', () => {
  it('should calculate spectral balance from EQ parameters', () => {
    const service = new AudioAttributeCalculationService()

    // Low bass, normal air → dark spectrum
    expect(service.calculateSpectralBalance({ bass_boost: 0, air_boost: 0 }))
      .toBe(0.5) // neutral

    // High bass, low air → dark/bassy
    expect(service.calculateSpectralBalance({ bass_boost: 8, air_boost: 0 }))
      .toBeLessThan(0.3)

    // Low bass, high air → bright/treble-heavy
    expect(service.calculateSpectralBalance({ bass_boost: 0, air_boost: 6 }))
      .toBeGreaterThan(0.7)
  })
})
```

### Pattern 3: Real-Time Polling

```typescript
describe('Parameter Polling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockEnhancementAPI.getParameters.mockResolvedValue(initialParams)
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  it('should poll parameters every 2 seconds', async () => {
    render(<EnhancementPaneV2 />)

    // Initial fetch
    await waitFor(() => {
      expect(mockEnhancementAPI.getParameters).toHaveBeenCalledTimes(1)
    })

    // Fast-forward 2s
    vi.advanceTimersByTime(2000)

    // Should poll again
    await waitFor(() => {
      expect(mockEnhancementAPI.getParameters).toHaveBeenCalledTimes(2)
    })
  })
})
```

---

## Coverage Goals

| Phase | Component Count | Test Count | Coverage % | Notes |
|-------|-----------------|-----------|-----------|-------|
| Phase 1 (Completed) | 12 lib + 6 other | 204 tests | ~25% | Library components + shared |
| Phase 2 Library (Completed) | 12 | 86 tests | ~10% | All library views |
| **Phase 2 Enhancement (In Progress)** | 8 | **150 tests** | **+15%** | Parameter display & controls |
| **Phase 3 (Planned)** | 5 services | **80+ tests** | **+10-15%** | Hooks, services, state |
| **Total Goal** | 30+ components | **530+ tests** | **55%+** | Full frontend coverage |

---

## Success Criteria

✅ **Phase 2 Enhancement Complete When**:
1. All 8 components tested (EnhancementPaneV2, ProcessingParameters, etc.)
2. 150+ tests passing (no failures, no skipped)
3. Real-time parameter polling verified (2s intervals)
4. Audio attribute changes propagate end-to-end
5. Error states handled (offline, timeout, invalid data)
6. Accessibility requirements met (ARIA, keyboard nav)
7. Coverage increases from ~35% to ~45%

✅ **Phase 3 Complete When**:
1. All 5 services/hooks tested
2. 80+ tests passing
3. Parameter validation working for all ranges
4. Audio characteristic calculations verified
5. State management tested (context, history, undo)
6. Coverage reaches 55%+ overall

---

## Notes for Deep Experimentation

The user mentioned: *"We'll have to do some deep experimentation in the long term with that."*

This suggests ongoing work to understand:
- How different DSP parameter combinations affect audio perception
- Optimal ranges for loudness, EQ, compression based on genre
- Which parameters matter most for user perception of "enhanced" audio
- How to verify parameter changes actually improve audio quality

**Recommendation**: Document parameter change experiments in a separate file:
- `docs/guides/AUDIO_ATTRIBUTE_EXPERIMENTATION.md`
- Log real user listening tests and parameter effectiveness
- Track which parameter ranges produce best perceived quality
- Correlate with fingerprint system for intelligent parameter selection

---

## References

- Phase 1 Test Library: [PHASE1_TEST_IMPLEMENTATION_COMPLETE.md](../development/PHASE1_TEST_IMPLEMENTATION_COMPLETE.md)
- Audio Fingerprint System: [AUDIO_FINGERPRINT_GRAPH_SYSTEM.md](./AUDIO_FINGERPRINT_GRAPH_SYSTEM.md)
- Component Architecture: [docs/guides/UI_DESIGN_GUIDELINES.md](./UI_DESIGN_GUIDELINES.md)
- Testing Guidelines: [docs/development/TESTING_GUIDELINES.md](../development/TESTING_GUIDELINES.md)
