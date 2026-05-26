/**
 * Redux Store Configuration
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Central store for application state management with slices for:
 * - Player state (playback, current track, volume)
 * - Queue state (tracks, current index)
 * - Cache state (stats, health)
 * - Connection state (WebSocket, API, latency)
 *
 * Phase C.3: Component Testing & Integration
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { configureStore } from '@reduxjs/toolkit';
import playerReducer from './slices/playerSlice';
import queueReducer from './slices/queueSlice';
import cacheReducer from './slices/cacheSlice';
import connectionReducer from './slices/connectionSlice';
import { createErrorTrackingMiddleware } from './middleware/errorTrackingMiddleware';
import { createLoggerMiddleware } from './middleware/loggerMiddleware';

/**
 * Configure Redux store with all slices
 */
export const store = configureStore({
  reducer: {
    player: playerReducer,
    queue: queueReducer,
    cache: cacheReducer,
    connection: connectionReducer,
  },
  middleware: (getDefaultMiddleware) => {
    // #3622: gate dev-only middleware so production bundles don't ship the
    // logger code and don't print errors to user consoles.
    const chain = getDefaultMiddleware().concat(
      createErrorTrackingMiddleware({ logToConsole: import.meta.env.DEV })
    );
    return import.meta.env.DEV ? chain.concat(createLoggerMiddleware()) : chain;
  },
  devTools: import.meta.env.DEV,
});

// Export types
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

export default store;
