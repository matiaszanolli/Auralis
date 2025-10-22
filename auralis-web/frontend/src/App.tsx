import React from 'react';
import { ToastProvider } from './components/shared/Toast';
import { EnhancementProvider } from './contexts/EnhancementContext';
import ComfortableApp from './ComfortableApp';

function App() {
  return (
    <ToastProvider maxToasts={3}>
      <EnhancementProvider>
        <ComfortableApp />
      </EnhancementProvider>
    </ToastProvider>
  );
}

export default App;