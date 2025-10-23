import React from 'react';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './components/shared/Toast';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { EnhancementProvider } from './contexts/EnhancementContext';
import ComfortableApp from './ComfortableApp';

function App() {
  return (
    <ThemeProvider>
      <ToastProvider maxToasts={3}>
        <WebSocketProvider>
          <EnhancementProvider>
            <ComfortableApp />
          </EnhancementProvider>
        </WebSocketProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

export default App;