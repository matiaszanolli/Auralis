import React from 'react';
import { Provider } from 'react-redux';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './components/shared/Toast';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { EnhancementProvider } from './contexts/EnhancementContext';
import ComfortableApp from './ComfortableApp';
import HiddenAudioElement from './components/player/HiddenAudioElement';
import { store } from './store';

function App() {
  return (
    <Provider store={store}>
      <ThemeProvider>
        <ToastProvider maxToasts={3}>
          <WebSocketProvider>
            <EnhancementProvider>
              {/* Hidden audio element for browser autoplay policy compliance and audio streaming */}
              <HiddenAudioElement debug={true} />
              <ComfortableApp />
            </EnhancementProvider>
          </WebSocketProvider>
        </ToastProvider>
      </ThemeProvider>
    </Provider>
  );
}

export default App;