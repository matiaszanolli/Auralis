# Frontend Component Architecture & Design Patterns

**Document Purpose:** Establish clear patterns and conventions for component organization, avoiding duplication and maintaining consistency across the Auralis frontend codebase.

**Audience:** All frontend developers working on the Auralis React application

**Last Updated:** 2025-11-22

---

## Table of Contents

1. [Core Principles](#core-principles)
2. [Component Organization](#component-organization)
3. [Reusable Patterns](#reusable-patterns)
4. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
5. [Decision Trees](#decision-trees)
6. [Pattern Examples](#pattern-examples)

---

## Core Principles

### 1. Single Source of Truth
Each UI component should have **ONE canonical implementation**.

**Rule:** Never create multiple versions of the same component (e.g., `EnhancementToggle` vs. `EnhancementToggleV2`).

**When duplicating seems necessary:**
- Use facade re-exports with preset props (see Pattern 1)
- Extract a shared base component, derive variants via props
- Use composition to combine multiple components

### 2. Component Size Limit
Components should stay **under 300 lines** of code.

**When component exceeds 300 lines:**
1. Extract subcomponents (extract UI layers)
2. Extract custom hooks (extract logic)
3. Use compound components (complex feature patterns)

### 3. Domain Organization
Organize components by **domain/feature**, not by type.

**Good Structure:**
```
components/
├── shared/           (UI primitives: Button, Input, Modal, etc.)
├── enhancement-pane-v2/  (Feature domain)
├── player-bar-v2/    (Feature domain)
├── library/          (Feature domain)
├── navigation/       (UI domain)
└── settings/         (Feature domain)
```

**Avoid:**
```
components/
├── buttons/          ❌ Type-based (avoid)
├── inputs/           ❌ Type-based (avoid)
├── modals/           ❌ Type-based (avoid)
└── views/            ❌ Type-based (avoid)
```

### 4. Clear Boundaries
Components have clear responsibilities:
- **Shared UI Primitives:** Reusable across multiple domains
- **Domain-Specific Components:** Feature-specific, possibly co-located styles
- **Container/Layout Components:** Manage state, coordinate subcomponents

---

## Component Organization

### Shared Components (`components/shared/`)

**Purpose:** Reusable UI primitives and utilities used across multiple feature domains.

**Characteristics:**
- ✅ No domain-specific logic
- ✅ Highly parameterized (flexible via props)
- ✅ Used in 2+ feature domains
- ✅ Well-tested with comprehensive test coverage
- ✅ Single source of truth (no variants)

**Canonical Shared Components:**
```
shared/
├── EnhancementToggle.tsx        (301 lines, 3 usage contexts)
├── ContextMenu.tsx              (352 lines, 3+ usages)
├── EmptyState.tsx               (164 lines, canonical)
├── DropZone.tsx                 (296 lines)
├── LoadingSpinner.tsx
├── SkeletonLoader.tsx
├── Toast.tsx
├── KeyboardShortcutsHelp.tsx
├── AlbumArtDisplay.tsx
├── ProgressiveImage.tsx
├── TrackContextMenu.tsx          (315 lines)
└── __tests__/                   (Test files co-located)
```

**When to put a component in `shared/`:**
- ✅ Used in 2+ different feature domains
- ✅ No hard dependencies on specific feature state
- ✅ Parameterized to handle multiple use cases
- ✅ Generic name (not prefixed with domain like "EnhancementPane")

**Examples of Shared Components:**
- `EmptyState` - Used by library, enhancement-pane, dropzone
- `EnhancementToggle` - Used by player-bar and enhancement-pane (via facade)
- `ContextMenu` - Used by track row, playlist, artist list
- `DropZone` - Generic file upload component

### Domain-Specific Components

**Purpose:** Components tightly coupled to a specific feature domain.

**Characteristics:**
- ✅ Feature-specific logic and state
- ✅ Used primarily in one feature domain
- ✅ May have domain-specific styling
- ✅ Organized in feature-specific directory

**Example Domains:**
```
enhancement-pane-v2/
├── EnhancementPaneV2.tsx        (Main component)
├── ProcessingParameters.tsx
├── AudioCharacteristics.tsx
├── EnhancementToggle.tsx        (Re-export facade)
├── ParameterBar.tsx
├── ParameterChip.tsx
├── InfoBox.tsx
├── LoadingState.tsx
└── __tests__/

player-bar-v2/
├── PlayerBarV2.tsx              (Main component)
├── PlayerBarV2Connected.tsx
├── PlaybackControls.tsx
├── VolumeControl.tsx
├── TrackInfo.tsx
├── ProgressBar.tsx
├── EnhancementToggle.tsx        (Re-export facade)
├── progress/                    (Subfeature)
│   ├── SeekSlider.tsx
│   ├── CurrentTimeDisplay.tsx
│   ├── DurationDisplay.tsx
│   └── CrossfadeVisualization.tsx
├── lyrics/                      (Subfeature)
│   └── LyricsPanel.tsx
├── queue/                       (Subfeature)
│   └── TrackQueue.tsx
└── __tests__/

library/
├── CozyLibraryView.tsx
├── TrackListView.tsx
├── CozyAlbumGrid.tsx
├── CozyArtistList.tsx
├── GlobalSearch.tsx
├── EditMetadataDialog.tsx
├── AlbumDetailView.tsx
├── ArtistDetailView.tsx
├── (... 20+ more components)
├── *.styles.ts                  (Design tokens)
└── __tests__/
```

**When to create a domain-specific component:**
- ✅ Component uses feature-specific state/context
- ✅ Styling tightly tied to domain (rarely reused elsewhere)
- ✅ Primarily used in one feature
- ✅ Can still be extracted to shared if it becomes generic

### Container vs. Presentational Components

**Container Components** (Smart Components)
- Manage state and side effects
- Connect to Redux/Context
- Handle data fetching and business logic
- Pass data down to presentational components

**Pattern Example:**
```typescript
// Container: Manages state
export function PlayerBarV2Connected() {
  const { track, isPlaying } = usePlayer()
  const { audioContext } = useAudioContext()

  return (
    <PlayerBarV2
      track={track}
      isPlaying={isPlaying}
      onPlay={() => {...}}
    />
  )
}

// Presentational: Pure UI
export function PlayerBarV2(props: PlayerBarV2Props) {
  return (
    <Container>
      <TrackInfo track={props.track} />
      <PlaybackControls isPlaying={props.isPlaying} />
    </Container>
  )
}
```

---

## Reusable Patterns

### Pattern 1: Facade Re-exports (Variant Presets)

**Use Case:** A component needs to appear slightly different in different contexts, but the behavior is identical.

**Problem:** Instead of passing a prop every time, create a pre-configured facade.

**Solution:** Create a wrapper that presets props and re-exports.

**Example: EnhancementToggle**

**Canonical Implementation** (`shared/EnhancementToggle.tsx`):
```typescript
interface EnhancementToggleProps {
  isEnabled: boolean
  onChange: (enabled: boolean) => void
  variant?: 'button' | 'switch'  // New variant prop
  size?: 'small' | 'medium'
}

export function EnhancementToggle({
  isEnabled,
  onChange,
  variant = 'button',
  size = 'medium',
}: EnhancementToggleProps) {
  if (variant === 'switch') {
    return <SwitchVariant isEnabled={isEnabled} onChange={onChange} />
  }

  return <ButtonVariant isEnabled={isEnabled} onChange={onChange} size={size} />
}
```

**Facade 1** (`player-bar-v2/EnhancementToggle.tsx`):
```typescript
import { EnhancementToggle as BaseEnhancementToggle } from '@/components/shared'

// Pre-configured for player bar context (compact button)
export function EnhancementToggle(props: Omit<EnhancementToggleProps, 'variant'>) {
  return <BaseEnhancementToggle {...props} variant="button" size="small" />
}
```

**Facade 2** (`enhancement-pane-v2/EnhancementToggle.tsx`):
```typescript
import { EnhancementToggle as BaseEnhancementToggle } from '@/components/shared'

// Pre-configured for enhancement pane context (form switch)
export function EnhancementToggle(props: Omit<EnhancementToggleProps, 'variant'>) {
  return <BaseEnhancementToggle {...props} variant="switch" />
}
```

**Usage in Player Bar:**
```typescript
import { EnhancementToggle } from '@/components/player-bar-v2'

// Props are simpler - variant is preset
<EnhancementToggle isEnabled={true} onChange={handler} />
```

**Usage in Enhancement Pane:**
```typescript
import { EnhancementToggle } from '@/components/enhancement-pane-v2'

// Same simple interface, different presentation
<EnhancementToggle isEnabled={true} onChange={handler} />
```

**Benefits:**
- ✅ Single source of truth (shared/EnhancementToggle)
- ✅ Clear context in import path (which variant you're using)
- ✅ Type-safe (TypeScript knows preset props)
- ✅ Easier to test (fewer prop combinations)
- ✅ Easier for future developers (intent is explicit)

**When to use this pattern:**
- Component needs 90% the same logic, 10% different presentation
- Different variant is always used in the same way (consistent preset)
- Two+ contexts need the same component

**When NOT to use:**
- ❌ Too many different configurations (use composition instead)
- ❌ Different logic in different contexts (extract logic difference)
- ❌ Single usage context (no facade needed)

---

### Pattern 2: Composition-Based Menu (Data-Driven)

**Use Case:** Different parts of the UI need context menus with different actions, but same component.

**Problem:** Hardcoding menu items in component makes it inflexible and hard to extend.

**Solution:** Define actions as data, compose menu items dynamically.

**Example: ContextMenu**

**Action Definition:**
```typescript
interface ContextMenuAction {
  id: string
  label: string
  icon?: string
  action: () => void | Promise<void>
  divider?: boolean
  disabled?: boolean
}
```

**Canonical Menu Component** (`shared/ContextMenu.tsx`):
```typescript
interface ContextMenuProps {
  items: ContextMenuAction[]
  onAction?: (action: ContextMenuAction) => void
  showPlaylistSection?: boolean
  playlists?: Playlist[]
  isLoadingPlaylists?: boolean
  onAddToPlaylist?: (playlistId: number) => void
}

export function ContextMenu({ items, onAction, ...playlistProps }: ContextMenuProps) {
  return (
    <Menu>
      {items.map((item) => (
        <MenuItem key={item.id} onClick={() => onAction?.(item)}>
          {item.label}
        </MenuItem>
      ))}

      {playlistProps.showPlaylistSection && (
        <>
          <Divider />
          <Subheader>Add to Playlist</Subheader>
          {/* Playlist rendering logic */}
        </>
      )}
    </Menu>
  )
}
```

**Action Builders** (`shared/contextMenuActions.ts`):
```typescript
export function getTrackContextActions(track: Track): ContextMenuAction[] {
  return [
    {
      id: 'play-next',
      label: 'Play Next',
      action: () => queueService.playNext(track),
    },
    {
      id: 'add-to-queue',
      label: 'Add to Queue',
      action: () => queueService.enqueue(track),
    },
    {
      id: 'remove',
      label: 'Remove from Library',
      action: () => libraryService.deleteTrack(track.id),
    },
  ]
}

export function getAlbumContextActions(album: Album): ContextMenuAction[] {
  return [
    {
      id: 'play-all',
      label: 'Play Album',
      action: () => playerService.playAlbum(album),
    },
    {
      id: 'add-all',
      label: 'Add Album to Queue',
      action: () => queueService.enqueueAlbum(album),
    },
  ]
}
```

**Usage:**
```typescript
// In TrackRow
const actions = getTrackContextActions(track)
const [showMenu, setShowMenu] = useState(false)
const [playlists, setPlaylists] = useState([])

return (
  <ContextMenu
    items={actions}
    onAction={(action) => action.action()}
    showPlaylistSection
    playlists={playlists}
    onAddToPlaylist={handleAddToPlaylist}
  />
)
```

**Benefits:**
- ✅ Data-driven (actions are configuration, not code)
- ✅ Reusable (same component for different contexts)
- ✅ Testable (test action builders separately from menu)
- ✅ Extensible (add new actions without touching component)
- ✅ Type-safe (ContextMenuAction interface)

**When to use this pattern:**
- ✅ Menu items vary by context/data
- ✅ Multiple components need similar menus
- ✅ Menu actions might be added/removed dynamically
- ✅ Complex menu with many items

**When NOT to use:**
- ❌ Simple menu with 1-2 fixed items
- ❌ Menu has complex UI (use specialized component instead)
- ❌ Actions are tightly coupled to component logic

---

### Pattern 3: Custom Hooks for Stateful Logic

**Use Case:** Multiple components need the same stateful logic.

**Problem:** Duplicating state/logic in multiple components.

**Solution:** Extract logic into a custom hook, use in multiple components.

**Example:**

```typescript
// hooks/useLibrarySearch.ts
export function useLibrarySearch(initialQuery = '') {
  const [query, setQuery] = useState(initialQuery)
  const [results, setResults] = useState<SearchResults | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults(null)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const res = await searchService.search(q)
      setResults(res)
      setQuery(q)
    } catch (err) {
      setError(err as Error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  return { query, results, isLoading, error, search, setQuery }
}
```

**Usage in Multiple Components:**
```typescript
// GlobalSearch.tsx
function GlobalSearch() {
  const { query, results, isLoading, search } = useLibrarySearch()
  return (
    <SearchInput
      value={query}
      onChange={(val) => search(val)}
      isLoading={isLoading}
    />
  )
}

// AlbumDetailView.tsx
function AlbumDetailView() {
  const { results } = useLibrarySearch()
  return <SearchResults results={results} />
}
```

**Benefits:**
- ✅ No code duplication
- ✅ Easier to test (test hook separately from component)
- ✅ Cleaner components (logic extracted)
- ✅ Shareable across projects (reusable hook)

---

### Pattern 4: Compound Components

**Use Case:** A component is genuinely large and has multiple distinct visual/logical sections.

**Problem:** Single large component is hard to test and understand.

**Solution:** Break into compound components with clear structure.

**Example: Settings Dialog**

```typescript
// Main component orchestrates structure
interface SettingsDialogProps {
  open: boolean
  onClose: () => void
}

export function SettingsDialog({ open, onClose }: SettingsDialogProps) {
  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>Settings</DialogTitle>
      <DialogContent>
        <SettingsTabs>
          <SettingsTab label="Playback">
            <PlaybackSettings />
          </SettingsTab>
          <SettingsTab label="Enhancement">
            <EnhancementSettings />
          </SettingsTab>
          <SettingsTab label="Display">
            <DisplaySettings />
          </SettingsTab>
        </SettingsTabs>
      </DialogContent>
    </Dialog>
  )
}

// Sub-components handle their own section
function PlaybackSettings() {
  return (
    <SettingsSection>
      <SettingItem label="Volume" control={<VolumeSlider />} />
      <SettingItem label="Crossfade" control={<CrossfadeControl />} />
    </SettingsSection>
  )
}

function EnhancementSettings() {
  return (
    <SettingsSection>
      {/* Enhancement-specific settings */}
    </SettingsSection>
  )
}

function DisplaySettings() {
  return (
    <SettingsSection>
      {/* Display-specific settings */}
    </SettingsSection>
  )
}
```

**Benefits:**
- ✅ Each component handles one concern
- ✅ Each component under 300 lines
- ✅ Easier to test (test each setting section)
- ✅ Easier to maintain (change one section independently)
- ✅ Easier to reuse (SettingsSection, SettingItem are reusable)

**When to use this pattern:**
- ✅ Component has 2+ distinct visual sections
- ✅ Sections have independent logic
- ✅ Component exceeds 300 lines
- ✅ Want to test sections independently

---

## Anti-Patterns to Avoid

### ❌ Anti-Pattern 1: Component Versioning

**Problem:**
```typescript
// DON'T DO THIS
components/
├── EnhancementToggle.tsx        (Original)
├── EnhancementToggleV2.tsx      (New version)
├── EnhancementToggleV3.tsx      (Newer version)
```

**Why it's bad:**
- Confusion about which to use
- Code duplication
- Hard to migrate
- Difficult for new developers

**Solution:**
```typescript
// DO THIS INSTEAD
components/
├── shared/
│   └── EnhancementToggle.tsx    (Single source)
├── player-bar-v2/
│   └── EnhancementToggle.tsx    (Facade preset)
└── enhancement-pane-v2/
    └── EnhancementToggle.tsx    (Facade preset)
```

---

### ❌ Anti-Pattern 2: Specialized Duplicates

**Problem:**
```typescript
// DON'T DO THIS
components/shared/EmptyState.tsx      (Generic)
components/library/EmptyStateBox.tsx  (Library-specific)
components/library/EmptyStateWrapper.tsx  (Another variant)
```

**Why it's bad:**
- Maintenance nightmare (bug fix in 3 places)
- Inconsistent behavior
- Hard to choose which to use

**Solution:**
```typescript
// DO THIS INSTEAD - Use props for customization
interface EmptyStateProps {
  icon?: 'music' | 'search' | 'folder'
  title: string
  description?: string
  actionLabel?: string
  onAction?: () => void
}

// Same component, different usage
<EmptyState icon="music" title="No artists" />
<EmptyState icon="search" title="No results" />
<EmptyState icon="folder" title="No tracks" />
```

---

### ❌ Anti-Pattern 3: Type-Based Organization

**Problem:**
```typescript
// DON'T DO THIS
components/
├── buttons/        (Type-based)
├── inputs/         (Type-based)
├── modals/         (Type-based)
├── pages/          (Type-based)
```

**Why it's bad:**
- Doesn't reflect feature/domain structure
- Hard to find related components
- No clear ownership/responsibility
- Doesn't scale (where does SearchButton go?)

**Solution:**
```typescript
// DO THIS INSTEAD - Domain-based
components/
├── shared/              (Reusable primitives)
├── library/             (Library domain)
├── enhancement-pane-v2/ (Enhancement domain)
├── player-bar-v2/       (Player domain)
├── navigation/          (Navigation domain)
```

---

### ❌ Anti-Pattern 4: Giant Components (>500 lines)

**Problem:**
```typescript
// DON'T DO THIS
export function SettingsDialog() {
  // 652 lines of code
  // 5+ responsibilities
  // Hard to test
  // Hard to modify
}
```

**Why it's bad:**
- Impossible to understand at a glance
- Hard to test individual features
- High risk of bugs when modifying
- Violates Single Responsibility Principle

**Solution:**
```typescript
// DO THIS INSTEAD
export function SettingsDialog() {
  return (
    <Dialog>
      <PlaybackSettings />      {/* 100 lines */}
      <EnhancementSettings />   {/* 120 lines */}
      <DisplaySettings />       {/* 80 lines */}
      <LibrarySettings />       {/* 70 lines */}
    </Dialog>
  )
}
```

---

### ❌ Anti-Pattern 5: Hardcoded Domain Logic in Shared

**Problem:**
```typescript
// DON'T DO THIS
// components/shared/EmptyState.tsx
export function EmptyState(props) {
  if (props.type === 'libraryEmpty') {
    return <LibraryEmptyUI />
  } else if (props.type === 'searchEmpty') {
    return <SearchEmptyUI />
  }
  // Domain-specific logic in shared component
}
```

**Why it's bad:**
- Shared component depends on domain knowledge
- Can't reuse in other projects
- Hard to extend for new domains
- Testing is complex

**Solution:**
```typescript
// DO THIS INSTEAD - Parameterize
interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
}

export function EmptyState({ icon, title, description }: EmptyStateProps) {
  return (
    <Container>
      {icon && <Icon>{icon}</Icon>}
      <Title>{title}</Title>
      {description && <Description>{description}</Description>}
    </Container>
  )
}

// Domain uses shared component with custom data
<EmptyState
  icon={<MusicIcon />}
  title="Library is empty"
  description="Add songs to get started"
/>
```

---

## Decision Trees

### Decision 1: Should I Create a New Component?

```
┌─ Does this UI element appear in 2+ places?
├─ YES → Extract to shared/ (or domain if specialized)
└─ NO  → Keep as subcomponent in parent

┌─ Is the logic/styling always the same?
├─ YES → Create reusable component
└─ NO  → Use composition instead (children, render props)

┌─ Will it ever be used outside this feature domain?
├─ YES → Put in shared/
├─ NO  → Put in feature domain directory
└─ MAYBE → Start in domain, move to shared when needed
```

### Decision 2: Where Should I Put This Component?

```
┌─ Is it used in 2+ unrelated feature domains?
├─ YES → shared/ (reusable primitive)
├─ NO  → Is it domain-specific?
│  ├─ YES → feature-domain/ (e.g., enhancement-pane-v2/, library/)
│  └─ NO  → Is it a UI primitive (Button, Input, Modal)?
│     ├─ YES → shared/
│     └─ NO  → Where is it primarily used?
│        └─ [Domain] (same directory as parent)
└─ UNSURE → Start in feature domain, refactor to shared if pattern emerges
```

### Decision 3: How Should I Handle Variants?

```
┌─ Does the same component need different presentations?
├─ SAME LOGIC, 10% DIFFERENT UI
│  └─ Use props OR facade re-export pattern
├─ DIFFERENT LOGIC IN DIFFERENT CONTEXTS
│  └─ Extract logic difference (custom hook)
├─ COMPLETELY DIFFERENT COMPONENT
│  └─ Create separate component (different name)
└─ MINOR STYLE DIFFERENCE
   └─ Use CSS classes/styled-components with variant prop
```

### Decision 4: Should I Extract This Logic?

```
┌─ Is this state/logic used in 2+ components?
├─ YES → Extract to custom hook
└─ NO  → Keep in component

┌─ Is the component > 300 lines?
├─ YES → Extract logic to custom hook (and/or subcomponents)
└─ NO  → Acceptable as-is

┌─ Is this testable as separate logic?
├─ YES → Extract to custom hook (easier to test)
└─ NO  → Keep in component
```

---

## Pattern Examples

### Example 1: ✅ GOOD - Facade Re-export Pattern

**Problem:** `EnhancementToggle` needs to appear different in two contexts

**Solution: Single source + re-export facades**

```
components/
├── shared/
│   └── EnhancementToggle.tsx          (301 lines, parametrized)
│
├── player-bar-v2/
│   ├── EnhancementToggle.tsx          (41 lines, re-export with variant='button')
│   └── PlayerBarV2.tsx
│
└── enhancement-pane-v2/
    ├── EnhancementToggle.tsx          (52 lines, re-export with variant='switch')
    └── EnhancementPaneV2.tsx
```

**shared/EnhancementToggle.tsx:**
```typescript
interface Props {
  isEnabled: boolean
  onChange: (enabled: boolean) => void
  variant?: 'button' | 'switch'
}

export function EnhancementToggle({ variant = 'button', ...props }: Props) {
  if (variant === 'switch') return <SwitchVersion {...props} />
  return <ButtonVersion {...props} />
}
```

**player-bar-v2/EnhancementToggle.tsx:**
```typescript
import { EnhancementToggle as Base } from '@/components/shared'
export function EnhancementToggle(props: Omit<Props, 'variant'>) {
  return <Base {...props} variant="button" />
}
```

**Benefits:**
- ✅ Single source of truth
- ✅ Clear intent (import path shows variant)
- ✅ Easy to update everywhere
- ✅ Type-safe

---

### Example 2: ✅ GOOD - Composition-Based Menu

**Problem:** Track menus, album menus, artist menus all have different items but same UI

**Solution: Data-driven actions + composition**

```typescript
// Define actions as data
interface ContextMenuAction {
  id: string
  label: string
  action: () => void
}

// Action builders (pure functions)
function getTrackActions(track: Track): ContextMenuAction[] {
  return [
    { id: 'play', label: 'Play', action: () => player.play(track) },
    { id: 'queue', label: 'Queue', action: () => queue.add(track) },
  ]
}

// Generic menu component
function ContextMenu({ items, onAction }: Props) {
  return (
    <Menu>
      {items.map(item => (
        <MenuItem key={item.id} onClick={() => onAction?.(item)}>
          {item.label}
        </MenuItem>
      ))}
    </Menu>
  )
}

// Usage - flexible and reusable
<ContextMenu items={getTrackActions(track)} onAction={handleAction} />
```

**Benefits:**
- ✅ One menu component for all types
- ✅ Actions are testable data
- ✅ Easy to add/remove items
- ✅ No conditional rendering hell

---

### Example 3: ✅ GOOD - Custom Hook Extraction

**Problem:** Multiple components need library search logic

**Solution: Extract to custom hook**

```typescript
// hooks/useLibrarySearch.ts
export function useLibrarySearch(initialQuery = '') {
  const [query, setQuery] = useState(initialQuery)
  const [results, setResults] = useState<SearchResults | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const search = useCallback(async (q: string) => {
    setIsLoading(true)
    const res = await searchService.search(q)
    setResults(res)
  }, [])

  return { query, results, isLoading, search, setQuery }
}

// GlobalSearch.tsx - uses hook
function GlobalSearch() {
  const { results, isLoading, search } = useLibrarySearch()
  return <SearchInput onChange={search} />
}

// DetailView.tsx - uses same hook
function DetailView() {
  const { results } = useLibrarySearch()
  return <SearchResults results={results} />
}
```

**Benefits:**
- ✅ Logic in one place
- ✅ Easy to test (test hook + component separately)
- ✅ Reusable across components
- ✅ No code duplication

---

### Example 4: ✅ GOOD - Compound Components

**Problem:** SettingsDialog is 650+ lines with 4 distinct sections

**Solution: Break into sub-components**

```typescript
// Main orchestrator (< 100 lines)
export function SettingsDialog({ open, onClose }: Props) {
  return (
    <Dialog open={open} onClose={onClose}>
      <SettingsTabs>
        <Tab label="Playback">
          <PlaybackSettings />
        </Tab>
        <Tab label="Enhancement">
          <EnhancementSettings />
        </Tab>
        <Tab label="Display">
          <DisplaySettings />
        </Tab>
        <Tab label="Library">
          <LibrarySettings />
        </Tab>
      </SettingsTabs>
    </Dialog>
  )
}

// Each section handles its own state (< 150 lines each)
function PlaybackSettings() { /* settings UI */ }
function EnhancementSettings() { /* settings UI */ }
function DisplaySettings() { /* settings UI */ }
function LibrarySettings() { /* settings UI */ }
```

**Benefits:**
- ✅ Each component under 300 lines
- ✅ Each handles one concern
- ✅ Easy to test sections independently
- ✅ Easy to modify individual sections
- ✅ Clear responsibility boundaries

---

### Example 5: ❌ BAD - Don't Do This

**Problem: Creating specialized duplicates**

```typescript
// ❌ WRONG
components/shared/EmptyState.tsx        (generic, 164 lines)
components/library/EmptyStateBox.tsx    (specialized, 63 lines)
components/library/LibraryEmptyState.tsx (another variant, 58 lines)
```

**Fix: Use single component with props**

```typescript
// ✅ CORRECT
components/shared/EmptyState.tsx        (single source, 164 lines)

// Usage: parameterize instead of duplicate
<EmptyState icon="music" title="No artists found" />
<EmptyState icon="search" title="No search results" />
<EmptyState icon="folder" title="Library empty" />
```

---

## Summary Checklist

When creating or refactoring a component, use this checklist:

- [ ] **Single Source of Truth:** Is there already a similar component? If yes, use it or refactor.
- [ ] **Size Check:** Is component under 300 lines? If no, extract subcomponents or logic.
- [ ] **Parameterization:** Can props handle different use cases instead of versioning?
- [ ] **Clear Intent:** Would import path make it clear what this component does?
- [ ] **Reusability:** Will this be used in 2+ places? If yes, consider `shared/`.
- [ ] **Testing:** Can this component be tested independently?
- [ ] **Documentation:** Are props well-documented? Does it have examples?
- [ ] **Dependencies:** Does this depend on domain-specific logic? If yes, should be in domain folder.
- [ ] **Naming:** Is the name clear about what it does? No "V2" or "Enhanced" versions?
- [ ] **Tests:** Do tests exist? Are they comprehensive?

---

## References

- [Component Consolidation Roadmap](./COMPONENT_CONSOLIDATION_ROADMAP.md)
- [CLAUDE.md - Component Guidelines](./CLAUDE.md#-component-guidelines)
- [React Documentation - Composition vs Inheritance](https://react.dev/learn/composition-vs-inheritance)
- [Airbnb React Style Guide](https://github.com/airbnb/javascript/tree/master/react)

---

**Last Updated:** 2025-11-22
**Maintained By:** Frontend Architecture Team
**Status:** Active - Reference Document
