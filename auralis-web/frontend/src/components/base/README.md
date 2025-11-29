# Base Component Library

**Phase A.5 Deliverable** - Foundation for modern, accessible React components

## Overview

The Base Component Library provides 15+ building blocks for constructing the Auralis UI. All components:
- Follow the design system tokens (no hardcoded colors/spacing)
- Support TypeScript with strict typing
- Include comprehensive test coverage (80%+ target)
- Are < 300 lines of code for maintainability
- Support React 18+ and accessibility standards

## Components by Category

### Layout Components (3)

#### Container
Constrains content width with horizontal centering.

```tsx
import { Container } from '@/components/base';

<Container maxWidth="lg" padding="lg">
  <h1>Centered content</h1>
</Container>
```

**Props:**
- `maxWidth`: 'sm' | 'md' | 'lg' | 'xl' | 'full' (default: 'lg')
- `padding`: design token spacing key (default: 'lg')
- `className`: custom CSS class

#### Stack
Flexible box for stacking children with consistent spacing.

```tsx
import { Stack } from '@/components/base';

<Stack direction="column" spacing="md" align="center">
  <div>Item 1</div>
  <div>Item 2</div>
</Stack>
```

**Props:**
- `direction`: 'row' | 'column' (default: 'column')
- `spacing`: design token spacing key (default: 'md')
- `align`: flex alignment value (default: 'flex-start')
- `justify`: flex justification value (default: 'flex-start')
- `className`: custom CSS class

#### Grid
CSS Grid layout with responsive column sizing.

```tsx
import { Grid } from '@/components/base';

<Grid columns={3} spacing="md">
  <Card>Item 1</Card>
  <Card>Item 2</Card>
  <Card>Item 3</Card>
</Grid>
```

**Props:**
- `columns`: fixed number of columns (optional, auto-fit if omitted)
- `spacing`: design token spacing key (default: 'md')
- `minColWidth`: minimum column width for auto-fit (default: '200px')
- `className`: custom CSS class

### Input Components (3)

#### TextInput
Text field with optional label, error state, and icons.

```tsx
import { TextInput } from '@/components/base';

<TextInput
  label="Search"
  placeholder="Enter search term"
  error={searchError}
  helperText="Enter 3+ characters"
  startIcon={<SearchIcon />}
/>
```

**Props:**
- Extends HTML input attributes
- `label`: label text
- `error`: error message (if present, shows in red)
- `helperText`: helper text (hidden when error exists)
- `startIcon`: icon element before input
- `endIcon`: icon element after input
- `fullWidth`: stretch to container width

#### Checkbox
Standard checkbox with label and error state.

```tsx
import { Checkbox } from '@/components/base';

<Checkbox label="Accept terms" error="Must accept" />
```

**Props:**
- Extends HTML input attributes
- `label`: label text
- `error`: error message

#### Toggle
Boolean switch with label.

```tsx
import { Toggle } from '@/components/base';

<Toggle label="Enable notifications" />
```

**Props:**
- Extends HTML input attributes
- `label`: label text
- `error`: error message

### Display Components (5)

#### Button
Multi-variant button component.

```tsx
import { Button } from '@/components/base';

<Button
  variant="primary"
  size="md"
  loading={isLoading}
  onClick={handleClick}
>
  Click me
</Button>
```

**Props:**
- `variant`: 'primary' | 'secondary' | 'ghost' | 'danger' (default: 'primary')
- `size`: 'sm' | 'md' | 'lg' (default: 'md')
- `loading`: show loading state
- `fullWidth`: stretch to container width
- `startIcon`: icon before text
- `endIcon`: icon after text
- Extends HTML button attributes

#### Card
Container for grouped content with optional header/footer.

```tsx
import { Card } from '@/components/base';

<Card
  header="Settings"
  footer={<Button>Save</Button>}
  hoverable
>
  <TextInput label="Username" />
</Card>
```

**Props:**
- `header`: header content
- `footer`: footer content
- `hoverable`: lift on hover
- `className`: custom CSS class

#### Badge
Inline label for categorization.

```tsx
import { Badge } from '@/components/base';

<Badge variant="success" size="md">
  Completed
</Badge>
```

**Props:**
- `variant`: 'primary' | 'success' | 'warning' | 'error' | 'info' (default: 'primary')
- `size`: 'sm' | 'md' (default: 'md')
- `className`: custom CSS class

#### Alert
Alert message with optional icon and close button.

```tsx
import { Alert } from '@/components/base';

<Alert variant="error" onClose={handleClose}>
  An error occurred while saving
</Alert>
```

**Props:**
- `variant`: 'info' | 'success' | 'warning' | 'error' (default: 'info')
- `icon`: icon element
- `onClose`: callback when close button clicked
- `className`: custom CSS class

#### ProgressBar
Visual progress indicator.

```tsx
import { ProgressBar } from '@/components/base';

<ProgressBar
  value={65}
  max={100}
  label="Upload progress"
  showValue
  color="primary"
/>
```

**Props:**
- `value`: current progress value
- `max`: maximum value (default: 100)
- `label`: label text
- `showValue`: display percentage
- `color`: 'primary' | 'success' | 'warning' | 'error' (default: 'primary')
- `size`: 'sm' | 'md' | 'lg' (default: 'md')
- `className`: custom CSS class

### Feedback Components (4)

#### LoadingSpinner
Animated loading indicator.

```tsx
import { LoadingSpinner } from '@/components/base';

<LoadingSpinner size="md" label="Loading..." />
```

**Props:**
- `size`: 'sm' | 'md' | 'lg' (default: 'md')
- `color`: color value (default: primary accent)
- `label`: optional label text
- `className`: custom CSS class

#### Modal
Dialog container with backdrop.

```tsx
import { Modal } from '@/components/base';
import { useState } from 'react';

function ConfirmDialog() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <Button onClick={() => setIsOpen(true)}>Open Modal</Button>
      <Modal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Confirm Action"
        size="md"
        footer={
          <Stack direction="row" spacing="md">
            <Button onClick={() => setIsOpen(false)}>Cancel</Button>
            <Button variant="primary">Confirm</Button>
          </Stack>
        }
      >
        Are you sure you want to proceed?
      </Modal>
    </>
  );
}
```

**Props:**
- `isOpen`: controls visibility
- `onClose`: callback when modal should close
- `title`: header text
- `size`: 'sm' | 'md' | 'lg' (default: 'md')
- `footer`: footer content
- `className`: custom CSS class

#### Tooltip
Hover tooltip for additional information.

```tsx
import { Tooltip } from '@/components/base';

<Tooltip content="Click to download" position="top">
  <Button>Download</Button>
</Tooltip>
```

**Props:**
- `content`: tooltip text
- `position`: 'top' | 'right' | 'bottom' | 'left' (default: 'top')
- `className`: custom CSS class

#### ErrorBoundary
React error boundary with recovery UI.

```tsx
import { ErrorBoundary } from '@/components/base';

<ErrorBoundary onError={(error, info) => console.log(error)}>
  <MyComponent />
</ErrorBoundary>
```

**Props:**
- `children`: component tree to protect
- `fallback`: custom error UI function
- `onError`: error callback (error, errorInfo)

## Design System Integration

All components use tokens from `@/design-system/tokens.ts`:

```tsx
import { tokens } from '@/design-system';

// Colors
tokens.colors.bg.primary        // Deep navy background
tokens.colors.accent.primary    // Aurora purple
tokens.colors.text.primary      // White text

// Spacing
tokens.spacing.sm   // 8px
tokens.spacing.md   // 16px
tokens.spacing.lg   // 24px

// Typography
tokens.typography.fontSize.base    // 14px
tokens.typography.fontWeight.semibold // 600

// Shadows
tokens.shadows.md   // Standard shadow

// Transitions
tokens.transitions.base  // 200ms ease
```

## Testing

All components include comprehensive tests:

```bash
# Run base component tests
npm run test base-components

# Run with coverage
npm run test:memory -- base-components --coverage
```

**Test Coverage:**
- Rendering: Does it render correctly?
- Props: Do props work as expected?
- Events: Do event handlers fire?
- States: Do state changes work?
- Accessibility: Are labels connected properly?
- Integration: Do components work together?

### Example Test
```tsx
import { render, screen } from '@/test/test-utils';
import { Button } from '../Button';

describe('Button', () => {
  it('renders with text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('calls onClick handler', () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);
    screen.getByText('Click').click();
    expect(onClick).toHaveBeenCalled();
  });
});
```

## Migration & Usage in App

To use components in pages:

```tsx
import {
  Container,
  Stack,
  Button,
  Card,
  TextInput,
} from '@/components/base';

export function SettingsPage() {
  return (
    <Container maxWidth="md">
      <Card header="Profile Settings">
        <Stack spacing="lg">
          <TextInput label="Username" />
          <TextInput label="Email" type="email" />
          <Stack direction="row" spacing="md" justify="flex-end">
            <Button variant="secondary">Cancel</Button>
            <Button variant="primary">Save</Button>
          </Stack>
        </Stack>
      </Card>
    </Container>
  );
}
```

## File Structure

```
src/components/base/
├── index.ts                      # All exports
├── README.md                     # This file
├── Container.tsx                 # Layout (45 lines)
├── Stack.tsx                     # Layout (40 lines)
├── Grid.tsx                      # Layout (35 lines)
├── TextInput.tsx                 # Input (95 lines)
├── Checkbox.tsx                  # Input (55 lines)
├── Toggle.tsx                    # Input (60 lines)
├── Button.tsx                    # Display (95 lines)
├── Card.tsx                      # Display (65 lines)
├── Badge.tsx                     # Display (65 lines)
├── Alert.tsx                     # Display (75 lines)
├── ProgressBar.tsx               # Display (75 lines)
├── LoadingSpinner.tsx            # Feedback (55 lines)
├── Modal.tsx                     # Feedback (95 lines)
├── Tooltip.tsx                   # Feedback (65 lines)
├── ErrorBoundary.tsx             # Feedback (95 lines)
└── __tests__/
    └── base-components.test.tsx  # 450+ test cases
```

**Total:** 15 components, ~1,000 lines of code, 80%+ coverage

## Next Steps

1. **Storybook Integration** (Phase A.5 continued)
   - Document components with live examples
   - Design token showcase
   - Accessibility checklist

2. **Phase B Integration** (Week 3)
   - Use in Player component
   - Use in Library search
   - Use in Settings dialog

3. **Component Expansion** (Phase C)
   - Select/ComboBox (complex input)
   - Tabs component
   - Breadcrumb navigation
   - Data Table component

## Standards

- **Max 300 lines** per component
- **Design tokens only** (no hardcoded values)
- **TypeScript strict** mode
- **80%+ test coverage** required
- **Accessibility** (semantic HTML, ARIA labels)
- **React 18+ hooks** (no class components except ErrorBoundary)
- **Forward refs** for all components
- **Display names** for debugging

## References

- [Design Tokens](../../design-system/tokens.ts)
- [Testing Guidelines](../../../docs/development/TESTING_GUIDELINES.md)
- [Component Architecture ADR](../../../docs/ADR-004-COMPONENT-ARCHITECTURE.md)
- [Accessibility Standards](../../../DEVELOPMENT_STANDARDS.md#accessibility)

---

**Phase A.5 - Base Component Library**
**Last Updated**: 2024-11-28
**Status**: Ready for Phase B Integration
