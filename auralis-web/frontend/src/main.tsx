import React from 'react';
import ReactDOM from 'react-dom/client';

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
    const { ThemeProvider } = await import('@mui/material/styles');
    const { default: CssBaseline } = await import('@mui/material/CssBaseline');
    const { Global } = await import('@emotion/react');
    const { globalStyles } = await import('./styles/globalStyles');
    const { default: App } = await import('./App');

    // Log commit ID for debugging
    const commitId = import.meta.env.VITE_COMMIT_ID || 'unknown';
    const commitMeta = document.querySelector('meta[name="commit-id"]');
    const commitFromMeta = commitMeta?.getAttribute('content') || 'unknown';
    console.log(`%c<µ Auralis ${import.meta.env.MODE} build`, 'color: #00d4ff; font-weight: bold; font-size: 14px;');
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
        <CssBaseline />
        <Global styles={globalStyles} />
        <App />
      </React.StrictMode>
    );

    console.log('[app] Application initialized successfully');
  } catch (err) {
    console.error('[app] Failed to initialize application:', err);
    const msg = (err instanceof Error) ? err.message : String(err);
    const stack = (err instanceof Error && err.stack) ? err.stack : 'No stack trace available';
    document.documentElement.innerHTML = '<body style="background:#1a1a1a;color:#fff;font-family:sans-serif;margin:0;padding:0;display:flex;align-items:center;justify-content:center;height:100vh"><div style="text-align:center;max-width:700px;padding:40px"><h1 style="color:#ff6b6b;margin:0 0 20px;font-size:28px">Initialization Error</h1><p style="color:#ccc;margin:0 0 20px;font-size:16px">Failed to initialize application</p><p style="color:#999;margin:0 0 20px;font-size:14px;font-family:monospace">' + msg + '</p><details style="text-align:left;margin:30px 0;padding:20px;background:#222;border:1px solid #444;border-radius:6px"><summary style="color:#667eea;cursor:pointer;font-weight:bold;margin-bottom:10px">Stack Trace</summary><pre style="color:#888;font-size:11px;overflow-x:auto;margin:0;white-space:pre-wrap;word-break:break-word;line-height:1.4">' + stack.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</pre></details></div></body>';
  }
})();
