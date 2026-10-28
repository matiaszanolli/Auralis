import { Provider } from 'react-redux';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './components/shared/Toast';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { PlaybackSessionProvider } from './contexts/PlaybackSessionContext';

import { StarfieldBackground } from './components/background';
import ComfortableApp from './ComfortableApp';
import { usePlayerStateSync } from '@/hooks/player/usePlayerStateSync';
import { useServerRestartNotice } from '@/hooks/player/useServerRestartNotice';
import { useWebSocketErrors } from '@/hooks/websocket/useWebSocketErrors';
import { useShowVisualizations } from '@/hooks/shared/useShowVisualizations';
import { useLibraryChangeSync } from '@/hooks/library/useLibraryChangeSync';
import { store } from './store';
import { shouldRetryQuery } from '@/utils/queryRetry';
import { QUERY_STALE_TIME_MS } from '@/config/timing';

// Create QueryClient instance
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: QUERY_STALE_TIME_MS,
      refetchOnWindowFocus: false,
      // Status-aware: transport failures, 408/429 and 5xx only (#5387).
      retry: shouldRetryQuery,
    },
  },
});

/**
 * PlayerStateSync - Inner component that uses WebSocket hook
 * Must be nested inside WebSocketProvider
 */
function PlayerStateSync() {
  // Synchronize WebSocket player_state messages to Redux
  usePlayerStateSync();
  // Surface WS security errors (rate-limit, schema validation) via toast (#2874)
  useWebSocketErrors();
  // Say so when a backend restart dropped the playback session (#5487)
  useServerRestartNotice();
  // Re-read the album caches when the library changes (#5871)
  useLibraryChangeSync();
  return null;
}

/**
 * AppContent - Main app content with all providers
 */
function AppContent() {
  // The "Show visualizations" switch controls the ambient background (#5676). Reduced motion is
  // handled inside StarfieldBackground, which draws one static frame.
  const showVisualizations = useShowVisualizations();
  return (
    <ThemeProvider>
      {/* GPU-accelerated starfield background with audio reactivity. Hosts the
          visualization wiring itself since #5661; AudioReactiveStarfield was a
          pass-through wrapper with nothing left to wrap. */}
      {showVisualizations && <StarfieldBackground className="app-ambient-background" />}
      <ToastProvider maxToasts={3}>
        <WebSocketProvider>
          {/* PlayerStateSync hook must be inside WebSocketProvider */}
          <PlayerStateSync />
          {/* Single shared enhanced-audio session (#4541) — both Player.tsx's
              transport bar and ComfortableApp's global keyboard shortcuts
              consume the same PlaybackSessionProvider instance. */}
          <PlaybackSessionProvider>
            <ComfortableApp />
          </PlaybackSessionProvider>
        </WebSocketProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

function App() {
  return (
    <Provider store={store}>
      <QueryClientProvider client={queryClient}>
        <AppContent />
      </QueryClientProvider>
    </Provider>
  );
}

export default App;
