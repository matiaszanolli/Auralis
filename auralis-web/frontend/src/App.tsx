import { Provider } from 'react-redux';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './components/shared/Toast';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { EnhancementProvider } from './contexts/EnhancementContext';
import { StarfieldBackground } from './components/background';
import ComfortableApp from './ComfortableApp';
import { usePlayerStateSync } from '@/hooks/player/usePlayerStateSync';
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
  return null; // This hook just sets up the sync, doesn't render anything
}

/**
 * AppContent - Main app content with all providers
 */
function AppContent() {
  return (
    <ThemeProvider>
      {/* GPU-accelerated starfield background */}
      <StarfieldBackground />
      <ToastProvider maxToasts={3}>
        <WebSocketProvider>
          {/* PlayerStateSync hook must be inside WebSocketProvider */}
          <PlayerStateSync />
          <EnhancementProvider>
            {/* Audio streaming handled exclusively via WebSocket using usePlayEnhanced hook */}
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
      <QueryClientProvider client={queryClient}>
        <AppContent />
      </QueryClientProvider>
    </Provider>
  );
}

export default App;