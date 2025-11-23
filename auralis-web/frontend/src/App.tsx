import React from 'react';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './components/shared/ui/feedback';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { EnhancementProvider } from './contexts/EnhancementContext';
import ComfortableApp from './ComfortableApp';
import HiddenAudioElement from './components/player/HiddenAudioElement';

function App() {
  return (
    <ThemeProvider>
      <ToastProvider maxToasts={3}>
        <WebSocketProvider>
          <EnhancementProvider>
            {/* Hidden audio element for browser autoplay policy compliance */}
            <HiddenAudioElement debug={false} />
            <ComfortableApp />
          </EnhancementProvider>
        </WebSocketProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

export default App;