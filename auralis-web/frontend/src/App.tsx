import { Provider } from 'react-redux';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './components/shared/Toast';
import { WebSocketProvider } from './contexts/WebSocketContext';

import { AudioReactiveStarfield } from './components/background';
import ComfortableApp from './ComfortableApp';
import { usePlayerStateSync } from '@/hooks/player/usePlayerStateSync';
import { useWebSocketErrors } from '@/hooks/websocket/useWebSocketErrors';
import { store } from './store';

// Create QueryClient instance
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      refetchOnWindowFocus: false,
      retry: 1,
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
  return null;
}

/**
 * AppContent - Main app content with all providers
 */
function AppContent() {
  return (
    <ThemeProvider>
      {/* GPU-accelerated starfield background with audio reactivity */}
      <AudioReactiveStarfield />
      <ToastProvider maxToasts={3}>
        <WebSocketProvider>
          {/* PlayerStateSync hook must be inside WebSocketProvider */}
          <PlayerStateSync />
          {/* Audio streaming handled exclusively via WebSocket using usePlayEnhanced hook */}
          <ComfortableApp />
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