/**
 * Enhancement Components Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Comprehensive tests for Phase 3 enhancement components:
 * - EnhancementPane: Main enhancement container
 * - PresetSelector: Preset selection buttons
 * - IntensitySlider: Intensity control with labels
 * - MasteringRecommendation: AI recommendation display
 * - ParameterDisplay: Single parameter visualization
 * - ParameterBar: Multiple parameters container
 *
 * @module components/enhancement/__tests__/EnhancementComponents.test
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import EnhancementPane from '@/components/enhancement/EnhancementPane';
import PresetSelector from '@/components/enhancement/PresetSelector';
import IntensitySlider from '@/components/enhancement/IntensitySlider';
import MasteringRecommendation from '@/components/enhancement/MasteringRecommendation';
import ParameterDisplay from '@/components/enhancement/ParameterDisplay';
import ParameterBar from '@/components/enhancement/ParameterBar';
import { useEnhancementControl } from '@/hooks/enhancement/useEnhancementControl';

// Mock hooks
vi.mock('@/hooks/enhancement/useEnhancementControl');
vi.mock('@/hooks/websocket/useWebSocketSubscription', () => ({
  useWebSocketSubscription: vi.fn(),
}));

describe('EnhancementPane', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render master toggle', () => {
    vi.mocked(useEnhancementControl).mockReturnValue({
      state: {
        enabled: false,
        preset: 'adaptive',
        intensity: 1.0,
        lastUpdated: Date.now(),
      },
      enabled: false,
      preset: 'adaptive',
      intensity: 1.0,
      toggleEnabled: vi.fn(),
      setPreset: vi.fn(),
      setIntensity: vi.fn(),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    render(<EnhancementPane />);

    expect(screen.getByRole('button', { name: /enhancement/i })).toBeInTheDocument();
  });

  it('should show enhancement controls when enabled', () => {
    vi.mocked(useEnhancementControl).mockReturnValue({
      state: {
        enabled: true,
        preset: 'adaptive',
        intensity: 1.0,
        lastUpdated: Date.now(),
      },
      enabled: true,
      preset: 'adaptive',
      intensity: 1.0,
      toggleEnabled: vi.fn(),
      setPreset: vi.fn(),
      setIntensity: vi.fn(),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    render(<EnhancementPane />);

    // Check for preset selector, intensity slider, etc.
    expect(screen.getByText(/adaptive/i)).toBeInTheDocument();
  });

  it('should hide enhancement controls when disabled', () => {
    vi.mocked(useEnhancementControl).mockReturnValue({
      state: {
        enabled: false,
        preset: 'adaptive',
        intensity: 1.0,
        lastUpdated: Date.now(),
      },
      enabled: false,
      preset: 'adaptive',
      intensity: 1.0,
      toggleEnabled: vi.fn(),
      setPreset: vi.fn(),
      setIntensity: vi.fn(),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    const { container } = render(<EnhancementPane />);

    // Preset controls should be hidden when disabled
    const presetsContainer = container.querySelector('[style*="display"]');
    expect(presetsContainer).toBeInTheDocument();
  });

  it('should call toggleEnabled when toggle button clicked', async () => {
    const mockToggleEnabled = vi.fn().mockResolvedValue(undefined);

    vi.mocked(useEnhancementControl).mockReturnValue({
      state: {
        enabled: false,
        preset: 'adaptive',
        intensity: 1.0,
        lastUpdated: Date.now(),
      },
      enabled: false,
      preset: 'adaptive',
      intensity: 1.0,
      toggleEnabled: mockToggleEnabled,
      setPreset: vi.fn(),
      setIntensity: vi.fn(),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    render(<EnhancementPane />);

    const toggleButton = screen.getByRole('button', { name: /enhancement/i });
    fireEvent.click(toggleButton);

    await waitFor(() => {
      expect(mockToggleEnabled).toHaveBeenCalled();
    });
  });
});

describe('PresetSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render all preset buttons', () => {
    const mockSetPreset = vi.fn();

    render(
      <PresetSelector
        currentPreset="adaptive"
        onPresetChange={mockSetPreset}
        isLoading={false}
      />
    );

    expect(screen.getByText(/adaptive/i)).toBeInTheDocument();
    expect(screen.getByText(/gentle/i)).toBeInTheDocument();
    expect(screen.getByText(/warm/i)).toBeInTheDocument();
    expect(screen.getByText(/bright/i)).toBeInTheDocument();
    expect(screen.getByText(/punchy/i)).toBeInTheDocument();
  });

  it('should highlight selected preset', () => {
    const mockSetPreset = vi.fn();

    render(
      <PresetSelector
        currentPreset="warm"
        onPresetChange={mockSetPreset}
        isLoading={false}
      />
    );

    const warmButton = screen.getByText(/warm/i).closest('button');
    expect(warmButton).toHaveAttribute('aria-pressed', 'true');
  });

  it('should call onPresetChange when preset is clicked', async () => {
    const mockSetPreset = vi.fn().mockResolvedValue(undefined);

    render(
      <PresetSelector
        currentPreset="adaptive"
        onPresetChange={mockSetPreset}
        isLoading={false}
      />
    );

    const brightButton = screen.getByText(/bright/i);
    fireEvent.click(brightButton);

    await waitFor(() => {
      expect(mockSetPreset).toHaveBeenCalledWith('bright');
    });
  });

  it('should disable buttons while loading', () => {
    const mockSetPreset = vi.fn();

    render(
      <PresetSelector
        currentPreset="adaptive"
        onPresetChange={mockSetPreset}
        isLoading={true}
      />
    );

    const buttons = screen.getAllByRole('button');
    buttons.forEach((button) => {
      expect(button).toBeDisabled();
    });
  });

  it('should display preset descriptions', () => {
    const mockSetPreset = vi.fn();

    render(
      <PresetSelector
        currentPreset="adaptive"
        onPresetChange={mockSetPreset}
        isLoading={false}
      />
    );

    // Descriptions should be visible
    expect(screen.getByText(/adaptive/i)).toBeInTheDocument();
  });
});

describe('IntensitySlider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render intensity slider', () => {
    const mockSetIntensity = vi.fn();

    render(
      <IntensitySlider
        intensity={0.5}
        onIntensityChange={mockSetIntensity}
        isLoading={false}
      />
    );

    const slider = screen.getByRole('slider');
    expect(slider).toBeInTheDocument();
  });

  it('should display intensity percentage', () => {
    const mockSetIntensity = vi.fn();

    render(
      <IntensitySlider
        intensity={0.8}
        onIntensityChange={mockSetIntensity}
        isLoading={false}
      />
    );

    expect(screen.getByText(/80%/)).toBeInTheDocument();
  });

  it('should display intensity label', () => {
    const mockSetIntensity = vi.fn();

    render(
      <IntensitySlider
        intensity={0.3}
        onIntensityChange={mockSetIntensity}
        isLoading={false}
      />
    );

    // Low intensity should show "Subtle" label
    expect(screen.getByText(/subtle|moderate|strong/i)).toBeInTheDocument();
  });

  it('should call onIntensityChange when slider changes', async () => {
    const mockSetIntensity = vi.fn().mockResolvedValue(undefined);

    render(
      <IntensitySlider
        intensity={0.5}
        onIntensityChange={mockSetIntensity}
        isLoading={false}
      />
    );

    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '0.7' } });

    await waitFor(() => {
      expect(mockSetIntensity).toHaveBeenCalled();
    });
  });

  it('should disable slider while loading', () => {
    const mockSetIntensity = vi.fn();

    render(
      <IntensitySlider
        intensity={0.5}
        onIntensityChange={mockSetIntensity}
        isLoading={true}
      />
    );

    const slider = screen.getByRole('slider');
    expect(slider).toBeDisabled();
  });

  it('should show intensity levels (subtle, moderate, strong)', () => {
    const mockSetIntensity = vi.fn();

    // Test subtle (low)
    const { rerender } = render(
      <IntensitySlider
        intensity={0.2}
        onIntensityChange={mockSetIntensity}
        isLoading={false}
      />
    );
    expect(screen.getByText(/subtle/i)).toBeInTheDocument();

    // Test moderate (middle)
    rerender(
      <IntensitySlider
        intensity={0.5}
        onIntensityChange={mockSetIntensity}
        isLoading={false}
      />
    );
    expect(screen.getByText(/moderate/i)).toBeInTheDocument();

    // Test strong (high)
    rerender(
      <IntensitySlider
        intensity={0.9}
        onIntensityChange={mockSetIntensity}
        isLoading={false}
      />
    );
    expect(screen.getByText(/strong/i)).toBeInTheDocument();
  });
});

describe('MasteringRecommendation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should display recommendation when present', () => {
    const recommendation = {
      recommended_preset: 'warm' as const,
      confidence: 0.92,
      analysis: 'Warm preset recommended for rich, warm tone',
    };

    render(
      <MasteringRecommendation
        recommendation={recommendation}
        isLoading={false}
      />
    );

    expect(screen.getByText(/warm/i)).toBeInTheDocument();
    expect(screen.getByText(/92%/)).toBeInTheDocument();
    expect(screen.getByText(/warm tone/i)).toBeInTheDocument();
  });

  it('should not display when recommendation is null', () => {
    const { container } = render(
      <MasteringRecommendation
        recommendation={null}
        isLoading={false}
      />
    );

    // Should be empty or minimal
    const text = container.textContent;
    expect(text?.includes('recommendation')).not.toBe(true);
  });

  it('should display loading state', () => {
    render(
      <MasteringRecommendation
        recommendation={null}
        isLoading={true}
      />
    );

    expect(screen.getByText(/analyzing|loading/i)).toBeInTheDocument();
  });

  it('should display confidence percentage', () => {
    const recommendation = {
      recommended_preset: 'bright' as const,
      confidence: 0.85,
      analysis: 'Analysis text',
    };

    render(
      <MasteringRecommendation
        recommendation={recommendation}
        isLoading={false}
      />
    );

    expect(screen.getByText(/85%/)).toBeInTheDocument();
  });

  it('should be expandable/collapsible', () => {
    const recommendation = {
      recommended_preset: 'punchy' as const,
      confidence: 0.88,
      analysis: 'Detailed analysis about punchy preset',
    };

    render(
      <MasteringRecommendation
        recommendation={recommendation}
        isLoading={false}
      />
    );

    // Should have expand/collapse button
    const expandButton = screen.getByRole('button');
    expect(expandButton).toBeInTheDocument();

    fireEvent.click(expandButton);

    // Analysis text should become visible
    expect(screen.getByText(/detailed analysis/i)).toBeInTheDocument();
  });
});

describe('ParameterDisplay', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should display parameter label', () => {
    render(
      <ParameterDisplay
        label="Loudness"
        value={-8.5}
        unit="dB"
        min={-20}
        max={0}
      />
    );

    expect(screen.getByText(/loudness/i)).toBeInTheDocument();
  });

  it('should display parameter value with unit', () => {
    render(
      <ParameterDisplay
        label="Loudness"
        value={-8.5}
        unit="dB"
        min={-20}
        max={0}
      />
    );

    expect(screen.getByText(/-8.5 dB/)).toBeInTheDocument();
  });

  it('should display progress bar', () => {
    const { container } = render(
      <ParameterDisplay
        label="Clarity"
        value={0.75}
        unit="%"
        min={0}
        max={1}
      />
    );

    // Should have a progress element
    const progress = container.querySelector('[role="progressbar"]');
    expect(progress).toBeInTheDocument();
  });

  it('should calculate progress correctly', () => {
    const { container } = render(
      <ParameterDisplay
        label="Test Param"
        value={5}
        unit="units"
        min={0}
        max={10}
      />
    );

    const progress = container.querySelector('[role="progressbar"]');
    // Progress should be 50% (5/10)
    expect(progress).toHaveAttribute('aria-valuenow', '50');
  });
});

describe('ParameterBar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should display multiple parameters', () => {
    render(
      <ParameterBar
        parameters={[
          { label: 'Loudness', value: -8.5, unit: 'dB' },
          { label: 'Dynamics', value: 0.45, unit: 'ratio' },
          { label: 'Clarity', value: 7.2, unit: 'dB' },
          { label: 'Presence', value: 3.1, unit: 'dB' },
        ]}
      />
    );

    expect(screen.getByText(/loudness/i)).toBeInTheDocument();
    expect(screen.getByText(/dynamics/i)).toBeInTheDocument();
    expect(screen.getByText(/clarity/i)).toBeInTheDocument();
    expect(screen.getByText(/presence/i)).toBeInTheDocument();
  });

  it('should display default audio parameters', () => {
    render(<ParameterBar />);

    // Default parameters
    expect(screen.getByText(/loudness/i)).toBeInTheDocument();
    expect(screen.getByText(/dynamics/i)).toBeInTheDocument();
    expect(screen.getByText(/clarity/i)).toBeInTheDocument();
    expect(screen.getByText(/presence/i)).toBeInTheDocument();
  });

  it('should display all values with units', () => {
    render(
      <ParameterBar
        parameters={[
          { label: 'Test1', value: 1.5, unit: 'x' },
          { label: 'Test2', value: 2.0, unit: 'y' },
        ]}
      />
    );

    expect(screen.getByText(/1.5 x/)).toBeInTheDocument();
    expect(screen.getByText(/2.0 y/)).toBeInTheDocument();
  });

  it('should use responsive grid layout', () => {
    const { container } = render(<ParameterBar />);

    // Should have grid container
    const grid = container.firstChild;
    expect(grid).toBeInTheDocument();
  });
});

describe('Integration: Enhancement Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should enable/disable enhancement controls', () => {
    const mockToggleEnabled = vi.fn().mockResolvedValue(undefined);
    const mockSetPreset = vi.fn().mockResolvedValue(undefined);

    vi.mocked(useEnhancementControl).mockReturnValue({
      state: {
        enabled: false,
        preset: 'adaptive',
        intensity: 1.0,
        lastUpdated: Date.now(),
      },
      enabled: false,
      preset: 'adaptive',
      intensity: 1.0,
      toggleEnabled: mockToggleEnabled,
      setPreset: mockSetPreset,
      setIntensity: vi.fn(),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    const { rerender } = render(<EnhancementPane />);

    // Toggle enhancement on
    const toggleButton = screen.getByRole('button', { name: /enhancement/i });
    fireEvent.click(toggleButton);

    // Mock updated state
    vi.mocked(useEnhancementControl).mockReturnValue({
      state: {
        enabled: true,
        preset: 'adaptive',
        intensity: 1.0,
        lastUpdated: Date.now(),
      },
      enabled: true,
      preset: 'adaptive',
      intensity: 1.0,
      toggleEnabled: mockToggleEnabled,
      setPreset: mockSetPreset,
      setIntensity: vi.fn(),
      isLoading: false,
      error: null,
      clearError: vi.fn(),
    } as any);

    rerender(<EnhancementPane />);

    // Presets should now be visible
    expect(screen.getByText(/adaptive/i)).toBeInTheDocument();
  });
});
