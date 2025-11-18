import React from 'react';
import ReactDOM from 'react-dom/client';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Global } from '@emotion/react';
import './index.css';
import App from './App';
import { auralisTheme } from './theme/auralisTheme';
import { globalStyles } from './styles/globalStyles';

// Log commit ID for debugging
const commitId = import.meta.env.VITE_COMMIT_ID || 'unknown';
const commitMeta = document.querySelector('meta[name="commit-id"]');
const commitFromMeta = commitMeta?.getAttribute('content') || 'unknown';
console.log(`%c🎵 Auralis ${import.meta.env.MODE} build`, 'color: #00d4ff; font-weight: bold; font-size: 14px;');
console.log(`%cCommit: ${commitFromMeta}`, 'color: #00d4ff; font-weight: bold;');
// Make commit info accessible globally for debugging
(window as any).__AURALIS_DEBUG__ = {
  commitId: commitFromMeta,
  buildMode: import.meta.env.MODE,
  version: '1.0.0-beta.13'
};

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <ThemeProvider theme={auralisTheme}>
      <CssBaseline />
      <Global styles={globalStyles} />
      <App />
    </ThemeProvider>
  </React.StrictMode>
);