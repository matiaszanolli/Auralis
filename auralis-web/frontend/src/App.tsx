import React from 'react';
import { ToastProvider } from './components/shared/Toast';
import ComfortableApp from './ComfortableApp';

function App() {
  return (
    <ToastProvider maxToasts={3}>
      <ComfortableApp />
    </ToastProvider>
  );
}

export default App;