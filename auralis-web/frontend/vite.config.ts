export default {
  server: {
    port: 3000,
    open: false,
  },
  build: {
    outDir: 'build',
    sourcemap: false,
  },
  esbuild: {
    jsxFactory: '_jsx',
    jsxFragment: '_Fragment',
    jsxImportSource: 'react',
  }
}
