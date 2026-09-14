/**
 * Redux State Hooks
 * ~~~~~~~~~~~~~~~~
 *
 * Convenience hooks for accessing Redux state and dispatching actions.
 * Provides a cleaner API for components instead of raw useSelector/useDispatch.
 *
 * Barrel (#5239): each Redux domain's hooks live in their own module, and this
 * file re-exports all of them so existing `@/hooks/shared/useReduxState`
 * imports keep working. New code can import the domain module directly.
 *
 * - usePlayerRedux:     usePlayerState, usePlayerActions, usePlayer, usePlaybackProgress
 * - useQueueRedux:      useQueueState, useQueue, useQueueTimeRemaining
 * - useCacheRedux:      useCacheState, useCache
 * - useConnectionRedux: useConnectionState, useConnection, useConnectionHealth
 * - useAppRedux:        useAppState, useIsLoading, useAppErrors (cross-slice)
 *
 * @copyright (C) 2024 Auralis Team
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

export * from '@/hooks/shared/usePlayerRedux';
export * from '@/hooks/shared/useQueueRedux';
export * from '@/hooks/shared/useCacheRedux';
export * from '@/hooks/shared/useConnectionRedux';
export * from '@/hooks/shared/useAppRedux';
