import { StrictMode } from 'react';
import ReactDOM from 'react-dom/client';

import { colors } from '@/design-system/tokens/colors';
import { buildFatalInitHtml } from '@/components/core/fatalInitScreen';

// Async IIFE to defer all component imports until dependencies are initialized
(async () => {
  try {
    // Import all MUI/emotion dependencies first
    await Promise.all([
      import('@mui/material/styles'),
      import('@mui/material'),
      import('@emotion/react'),
    ]);

    // Now safe to import components that use styled(Paper) etc
    const { ThemeProvider: _ThemeProvider } = await import('@mui/material/styles');
    const { default: CssBaseline } = await import('@mui/material/CssBaseline');
    const { Global } = await import('@emotion/react');
    const { globalStyles } = await import('./styles/globalStyles');
    const { default: App } = await import('./App');
    const { ErrorBoundary } = await import('./components/core/ErrorBoundary');

    // Log commit ID for debugging
    const commitMeta = document.querySelector('meta[name="commit-id"]');
    const commitFromMeta = commitMeta?.getAttribute('content') || 'unknown';
    const banner = `color: ${colors.accent.secondary}; font-weight: bold; font-size: 14px;`;
    console.log(`%c🎵 Auralis ${import.meta.env.MODE} build`, banner);
    console.log(`%cCommit: ${commitFromMeta}`, banner);
    // Make commit info accessible globally for debugging
    window.__AURALIS_DEBUG__ = {
      commitId: commitFromMeta,
      buildMode: import.meta.env.MODE,
      version: __APP_VERSION__
    };

    const root = ReactDOM.createRoot(
      document.getElementById('root') as HTMLElement
    );

    root.render(
      <StrictMode>
        <ErrorBoundary>
          <CssBaseline />
          <Global styles={globalStyles} />
          <App />
        </ErrorBoundary>
      </StrictMode>
    );

    console.log('[app] Application initialized successfully');
  } catch (err) {
    console.error('[app] Failed to initialize application:', err);
    const msg = (err instanceof Error) ? err.message : String(err);
    const stack = (err instanceof Error && err.stack) ? err.stack : 'No stack trace available';
    document.documentElement.innerHTML = buildFatalInitHtml(msg, stack);
  }
})();