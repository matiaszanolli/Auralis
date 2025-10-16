import React from 'react';
import ReactDOM from 'react-dom/client';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Global } from '@emotion/react';
import './index.css';
import App from './App';
import { auralisTheme } from './theme/auralisTheme';
import { globalStyles } from './styles/globalStyles';

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