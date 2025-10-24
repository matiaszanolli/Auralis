/**
 * EnhancementContext - Global state management for audio enhancement
 *
 * Manages enhancement settings (enabled, preset, intensity) and syncs
 * with backend via REST API and WebSocket updates.
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useWebSocketContext } from './WebSocketContext';

export interface EnhancementSettings {
  enabled: boolean;
  preset: 'adaptive' | 'gentle' | 'warm' | 'bright' | 'punchy';
  intensity: number; // 0.0 - 1.0
}

interface EnhancementContextType {
  settings: EnhancementSettings;
  setEnabled: (enabled: boolean) => void;
  setPreset: (preset: string) => void;
  setIntensity: (intensity: number) => void;
  isProcessing: boolean;
}

const EnhancementContext = createContext<EnhancementContextType | undefined>(undefined);

export const useEnhancement = () => {
  const context = useContext(EnhancementContext);
  if (!context) {
    throw new Error('useEnhancement must be used within EnhancementProvider');
  }
  return context;
};

interface EnhancementProviderProps {
  children: React.ReactNode;
}

export const EnhancementProvider: React.FC<EnhancementProviderProps> = ({ children }) => {
  const [settings, setSettings] = useState<EnhancementSettings>({
    enabled: false,
    preset: 'adaptive',
    intensity: 1.0,
  });
  const [isProcessing, setIsProcessing] = useState(false);

  // WebSocket for real-time sync (using shared WebSocketContext)
  const { subscribe } = useWebSocketContext();

  // Listen for WebSocket updates from backend
  useEffect(() => {
    console.log('🎨 EnhancementContext: Setting up WebSocket subscriptions');

    // Subscribe to enhancement_toggled
    const unsubscribeToggled = subscribe('enhancement_toggled', (message: any) => {
      try {
        setSettings(prev => ({
          ...prev,
          enabled: message.data.enabled,
          preset: message.data.preset,
          intensity: message.data.intensity,
        }));
      } catch (error) {
        console.error('Error handling enhancement_toggled:', error);
      }
    });

    // Subscribe to enhancement_preset_changed
    const unsubscribePreset = subscribe('enhancement_preset_changed', (message: any) => {
      try {
        setSettings(prev => ({
          ...prev,
          preset: message.data.preset,
          enabled: message.data.enabled,
          intensity: message.data.intensity,
        }));
      } catch (error) {
        console.error('Error handling enhancement_preset_changed:', error);
      }
    });

    // Subscribe to enhancement_intensity_changed
    const unsubscribeIntensity = subscribe('enhancement_intensity_changed', (message: any) => {
      try {
        setSettings(prev => ({
          ...prev,
          intensity: message.data.intensity,
          enabled: message.data.enabled,
          preset: message.data.preset,
        }));
      } catch (error) {
        console.error('Error handling enhancement_intensity_changed:', error);
      }
    });

    // Cleanup: unsubscribe from all message types
    return () => {
      console.log('🎨 EnhancementContext: Cleaning up WebSocket subscriptions');
      unsubscribeToggled();
      unsubscribePreset();
      unsubscribeIntensity();
    };
  }, [subscribe]);

  // Set enabled state via REST API
  const setEnabled = useCallback(async (enabled: boolean) => {
    try {
      setIsProcessing(true);
      const url = `http://localhost:8765/api/player/enhancement/toggle?enabled=${enabled}`;
      console.log('Calling enhancement toggle API:', url);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      console.log('Enhancement toggle response:', response.status, response.statusText);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Enhancement toggle failed:', errorText);
        throw new Error(`Failed to toggle enhancement: ${response.statusText} - ${errorText}`);
      }

      const data = await response.json();
      console.log('Enhancement toggle success:', data);

      // Update local state (WebSocket will also update it, but this is immediate)
      setSettings(prev => ({
        ...prev,
        enabled: data.settings.enabled,
      }));
    } catch (error) {
      console.error('Failed to set enhancement enabled:', error);
      throw error; // Re-throw so calling code knows it failed
    } finally {
      setIsProcessing(false);
    }
  }, []);

  // Set preset via REST API
  const setPreset = useCallback(async (preset: string) => {
    try {
      setIsProcessing(true);
      const response = await fetch(`/api/player/enhancement/preset?preset=${preset}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to set preset: ${response.statusText}`);
      }

      const data = await response.json();

      // Update local state
      setSettings(prev => ({
        ...prev,
        preset: data.settings.preset,
      }));
    } catch (error) {
      console.error('Failed to set enhancement preset:', error);
    } finally {
      setIsProcessing(false);
    }
  }, []);

  // Set intensity via REST API
  const setIntensity = useCallback(async (intensity: number) => {
    // Clamp between 0.0 and 1.0
    const clampedIntensity = Math.max(0.0, Math.min(1.0, intensity));

    try {
      setIsProcessing(true);
      const response = await fetch(`/api/player/enhancement/intensity?intensity=${clampedIntensity}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to set intensity: ${response.statusText}`);
      }

      const data = await response.json();

      // Update local state
      setSettings(prev => ({
        ...prev,
        intensity: data.settings.intensity,
      }));
    } catch (error) {
      console.error('Failed to set enhancement intensity:', error);
    } finally {
      setIsProcessing(false);
    }
  }, []);

  const value: EnhancementContextType = {
    settings,
    setEnabled,
    setPreset,
    setIntensity,
    isProcessing,
  };

  return (
    <EnhancementContext.Provider value={value}>
      {children}
    </EnhancementContext.Provider>
  );
};
