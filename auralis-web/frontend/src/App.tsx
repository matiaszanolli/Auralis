import React from 'react';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './components/shared/Toast';
import { EnhancementProvider } from './contexts/EnhancementContext';
import ComfortableApp from './ComfortableApp';

function App() {
  return (
    <ThemeProvider>
      <ToastProvider maxToasts={3}>
        <EnhancementProvider>
          <ComfortableApp />
        </EnhancementProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

export default App;