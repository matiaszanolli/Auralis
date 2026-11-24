# Frontend Documentation

Documentation for the React/TypeScript renderer in `auralis-web/frontend/`.

- [subsystems/frontend.md](../subsystems/frontend.md): architecture reference (app shell, Redux, hooks,
  API and WebSocket clients, design system, Web Audio pipeline). Start here.
- [PLAYER_ENHANCEMENT_ARCHITECTURE.md](PLAYER_ENHANCEMENT_ARCHITECTURE.md): the player bar and the
  enhancement pane as built.
- [testing/TESTING_COMMANDS.md](testing/TESTING_COMMANDS.md): pnpm and Vitest commands, and the CI gates.
- [../UI_STYLE_GUIDE.md](../UI_STYLE_GUIDE.md): visual language and the design tokens.
- [../development/DEVELOPMENT_SETUP_FRONTEND.md](../development/DEVELOPMENT_SETUP_FRONTEND.md): local setup.

Sprint-era analyses, implementation reports and component audits are in
[`docs/archive/frontend-history/`](../archive/frontend-history/).

Run the whole suite with `pnpm run test:memory`; the 2 GB heap prevents out-of-memory failures.

See the parent [README.md](../README.md) for the full documentation index.
