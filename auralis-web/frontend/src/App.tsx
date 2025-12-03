import React from 'react';
import { Provider } from 'react-redux';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './components/shared/Toast';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { EnhancementProvider } from './contexts/EnhancementContext';
import ComfortableApp from './ComfortableApp';
import HiddenAudioElement from './components/player/HiddenAudioElement';
import { usePlayerStateSync } from '@/hooks/player/usePlayerStateSync';
import { store } from './store';

/**
 * PlayerStateSync - Inner component that uses WebSocket hook
 * Must be nested inside WebSocketProvider
 */
function PlayerStateSync() {
  // Synchronize WebSocket player_state messages to Redux
  usePlayerStateSync();
  return null; // This hook just sets up the sync, doesn't render anything
}

/**
 * AppContent - Main app content with all providers
 */
function AppContent() {
  return (
    <ThemeProvider>
      <ToastProvider maxToasts={3}>
        <WebSocketProvider>
          {/* PlayerStateSync hook must be inside WebSocketProvider */}
          <PlayerStateSync />
          <EnhancementProvider>
            {/* Hidden audio element for browser autoplay policy compliance and audio streaming */}
            <HiddenAudioElement debug={true} />
            <ComfortableApp />
          </EnhancementProvider>
        </WebSocketProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

function App() {
  return (
    <Provider store={store}>
      <AppContent />
    </Provider>
  );
}

export default App;