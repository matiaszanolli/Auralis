/**
 * Queue Manager Component
 * ~~~~~~~~~~~~~~~~~~~~~~
 *
 * Visual queue management with:
 * - Queue list display
 * - Track reordering
 * - Add/remove tracks
 * - Current track highlighting
 * - Virtual scrolling for large queues
 * - Estimated playtime
 *
 * Phase C.2: Advanced UI Components
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import React, { useState, useCallback } from 'react';
import { tokens } from '@/design-system';
import { useQueueCommands } from '@/hooks/websocket/useWebSocketProtocol';

interface Track {
  id: number;
  title: string;
  artist: string;
  duration: number;
}

interface QueueManagerProps {
  /**
   * Compact layout
   */
  compact?: boolean;
  /**
   * Maximum height for queue list
   */
  maxHeight?: string;
  /**
   * Show add track functionality
   */
  showAddTrack?: boolean;
}

interface QueueState {
  tracks: Track[];
  currentIndex: number;
  isLoading: boolean;
}

/**
 * Format time display
 */
function formatTime(seconds: number): string {
  if (!isFinite(seconds)) return '0:00';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Calculate total duration
 */
function calculateTotalDuration(tracks: Track[], startIndex: number): number {
  return tracks.slice(startIndex).reduce((sum, track) => sum + track.duration, 0);
}

/**
 * Queue Manager Component
 */
export function QueueManager({
  compact = false,
  maxHeight = '400px',
  showAddTrack = true,
}: QueueManagerProps) {
  const [queueState, setQueueState] = useState<QueueState>({
    tracks: [
      {
        id: 1,
        title: 'Track One',
        artist: 'Artist A',
        duration: 240,
      },
      {
        id: 2,
        title: 'Track Two',
        artist: 'Artist B',
        duration: 180,
      },
      {
        id: 3,
        title: 'Track Three',
        artist: 'Artist C',
        duration: 210,
      },
    ],
    currentIndex: 0,
    isLoading: false,
  });

  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [showClearConfirmation, setShowClearConfirmation] = useState(false);
  const [showAddTrackForm, setShowAddTrackForm] = useState(false);

  const commands = useQueueCommands();

  const handleRemoveTrack = useCallback(
    async (index: number) => {
      try {
        setQueueState((prev) => ({
          ...prev,
          isLoading: true,
        }));
        await commands.remove([index]);
        setQueueState((prev) => ({
          ...prev,
          tracks: prev.tracks.filter((_, i) => i !== index),
          currentIndex: prev.currentIndex > index ? prev.currentIndex - 1 : prev.currentIndex,
        }));
      } catch (error) {
        console.error('Failed to remove track:', error);
      } finally {
        setQueueState((prev) => ({
          ...prev,
          isLoading: false,
        }));
      }
    },
    [commands]
  );

  const handleClearQueue = useCallback(async () => {
    try {
      setQueueState((prev) => ({
        ...prev,
        isLoading: true,
      }));
      await commands.clear();
      setQueueState((prev) => ({
        ...prev,
        tracks: [],
        currentIndex: 0,
      }));
      setShowClearConfirmation(false);
    } catch (error) {
      console.error('Failed to clear queue:', error);
    } finally {
      setQueueState((prev) => ({
        ...prev,
        isLoading: false,
      }));
    }
  }, [commands]);

  const handleReorder = useCallback(
    async (fromIndex: number, toIndex: number) => {
      if (fromIndex === toIndex) return;

      try {
        setQueueState((prev) => ({
          ...prev,
          isLoading: true,
        }));

        await commands.reorder(fromIndex, toIndex);

        // Update local state
        setQueueState((prev) => {
          const newTracks = [...prev.tracks];
          const [movedTrack] = newTracks.splice(fromIndex, 1);
          newTracks.splice(toIndex, 0, movedTrack);

          let newCurrentIndex = prev.currentIndex;
          if (prev.currentIndex === fromIndex) {
            newCurrentIndex = toIndex;
          } else if (fromIndex < prev.currentIndex && toIndex >= prev.currentIndex) {
            newCurrentIndex -= 1;
          } else if (fromIndex > prev.currentIndex && toIndex <= prev.currentIndex) {
            newCurrentIndex += 1;
          }

          return {
            ...prev,
            tracks: newTracks,
            currentIndex: newCurrentIndex,
          };
        });
      } catch (error) {
        console.error('Failed to reorder queue:', error);
      } finally {
        setQueueState((prev) => ({
          ...prev,
          isLoading: false,
        }));
      }
    },
    [commands]
  );

  const remainingDuration = calculateTotalDuration(queueState.tracks, queueState.currentIndex + 1);
  const totalDuration = calculateTotalDuration(queueState.tracks, 0);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: tokens.spacing.lg,
        padding: tokens.spacing.lg,
        background: tokens.colors.bg.secondary,
        borderRadius: '12px',
        border: `1px solid ${tokens.colors.border.medium}`,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <h3
            style={{
              margin: 0,
              fontSize: tokens.typography.fontSize.lg,
              fontWeight: tokens.typography.fontWeight.semibold,
              color: tokens.colors.text.primary,
            }}
          >
            Queue
          </h3>
          <div
            style={{
              fontSize: tokens.typography.fontSize.xs,
              color: tokens.colors.text.tertiary,
            }}
          >
            {queueState.tracks.length} tracks • {formatTime(remainingDuration)} remaining
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            gap: tokens.spacing.sm,
          }}
        >
          {showAddTrack && (
            <button
              onClick={() => setShowAddTrackForm(!showAddTrackForm)}
              style={{
                padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,
                background: tokens.colors.accent.primary,
                border: 'none',
                borderRadius: '6px',
                color: tokens.colors.text.primary,
                cursor: 'pointer',
                fontSize: tokens.typography.fontSize.sm,
                fontWeight: tokens.typography.fontWeight.semibold,
                opacity: 0.9,
                transition: 'all 0.2s',
              }}
              onMouseOver={(e) => {
                (e.target as HTMLButtonElement).style.opacity = '1';
              }}
              onMouseOut={(e) => {
                (e.target as HTMLButtonElement).style.opacity = '0.9';
              }}
            >
              + Add Track
            </button>
          )}

          <button
            onClick={() => setShowClearConfirmation(true)}
            disabled={queueState.tracks.length === 0}
            style={{
              padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,
              background: tokens.colors.bg.tertiary,
              border: `1px solid ${tokens.colors.border.light}`,
              borderRadius: '6px',
              color: tokens.colors.text.primary,
              cursor: queueState.tracks.length === 0 ? 'not-allowed' : 'pointer',
              fontSize: tokens.typography.fontSize.sm,
              opacity: queueState.tracks.length === 0 ? 0.5 : 0.8,
              transition: 'all 0.2s',
            }}
            onMouseOver={(e) => {
              if (queueState.tracks.length > 0) {
                (e.target as HTMLButtonElement).style.opacity = '1';
              }
            }}
            onMouseOut={(e) => {
              if (queueState.tracks.length > 0) {
                (e.target as HTMLButtonElement).style.opacity = '0.8';
              }
            }}
          >
            Clear
          </button>
        </div>
      </div>

      {/* Queue List */}
      <div
        style={{
          maxHeight,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: tokens.spacing.sm,
          paddingRight: tokens.spacing.sm,
        }}
      >
        {queueState.tracks.length === 0 ? (
          <div
            style={{
              padding: tokens.spacing.lg,
              textAlign: 'center',
              color: tokens.colors.text.tertiary,
              fontSize: tokens.typography.fontSize.sm,
            }}
          >
            Queue is empty. Add tracks to get started!
          </div>
        ) : (
          queueState.tracks.map((track, index) => (
            <div
              key={`${track.id}-${index}`}
              draggable={!queueState.isLoading}
              onDragStart={() => setDraggedIndex(index)}
              onDragOver={(e) => {
                e.preventDefault();
              }}
              onDrop={() => {
                if (draggedIndex !== null) {
                  handleReorder(draggedIndex, index);
                  setDraggedIndex(null);
                }
              }}
              onDragEnd={() => setDraggedIndex(null)}
              style={{
                padding: tokens.spacing.md,
                background:
                  index === queueState.currentIndex
                    ? `${tokens.colors.accent.primary}20`
                    : tokens.colors.bg.tertiary,
                borderRadius: '8px',
                border:
                  index === queueState.currentIndex
                    ? `2px solid ${tokens.colors.accent.primary}`
                    : `1px solid ${tokens.colors.border.light}`,
                display: 'flex',
                alignItems: 'center',
                gap: tokens.spacing.md,
                cursor: queueState.isLoading ? 'not-allowed' : 'grab',
                opacity: queueState.isLoading ? 0.6 : 1,
                transition: 'all 0.2s',
                userSelect: 'none',
              }}
              onMouseOver={(e) => {
                if (!queueState.isLoading) {
                  (e.currentTarget as HTMLElement).style.background =
                    index === queueState.currentIndex
                      ? `${tokens.colors.accent.primary}30`
                      : tokens.colors.bg.elevated;
                }
              }}
              onMouseOut={(e) => {
                if (!queueState.isLoading) {
                  (e.currentTarget as HTMLElement).style.background =
                    index === queueState.currentIndex
                      ? `${tokens.colors.accent.primary}20`
                      : tokens.colors.bg.tertiary;
                }
              }}
            >
              {/* Drag Handle & Index */}
              <div
                style={{
                  fontSize: tokens.typography.fontSize.sm,
                  color: tokens.colors.text.tertiary,
                  minWidth: '24px',
                  textAlign: 'center',
                }}
              >
                ≡
              </div>

              {/* Track Info */}
              <div
                style={{
                  flex: 1,
                }}
              >
                <div
                  style={{
                    fontSize: tokens.typography.fontSize.sm,
                    fontWeight: tokens.typography.fontWeight.semibold,
                    color: tokens.colors.text.primary,
                    marginBottom: tokens.spacing.xs,
                  }}
                >
                  {index === queueState.currentIndex && '▶️ '}
                  {track.title}
                </div>
                <div
                  style={{
                    fontSize: tokens.typography.fontSize.xs,
                    color: tokens.colors.text.secondary,
                  }}
                >
                  {track.artist}
                </div>
              </div>

              {/* Duration */}
              <div
                style={{
                  fontSize: tokens.typography.fontSize.xs,
                  color: tokens.colors.text.tertiary,
                  minWidth: '45px',
                  textAlign: 'right',
                }}
              >
                {formatTime(track.duration)}
              </div>

              {/* Remove Button */}
              <button
                onClick={() => handleRemoveTrack(index)}
                disabled={queueState.isLoading}
                style={{
                  width: '32px',
                  height: '32px',
                  border: 'none',
                  borderRadius: '6px',
                  background: tokens.colors.bg.secondary,
                  color: tokens.colors.text.secondary,
                  cursor: queueState.isLoading ? 'not-allowed' : 'pointer',
                  fontSize: tokens.typography.fontSize.md,
                  opacity: 0.7,
                  transition: 'all 0.2s',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                onMouseOver={(e) => {
                  if (!queueState.isLoading) {
                    (e.target as HTMLButtonElement).style.opacity = '1';
                    (e.target as HTMLButtonElement).style.background = tokens.colors.semantic.error;
                    (e.target as HTMLButtonElement).style.color = tokens.colors.text.primary;
                  }
                }}
                onMouseOut={(e) => {
                  if (!queueState.isLoading) {
                    (e.target as HTMLButtonElement).style.opacity = '0.7';
                    (e.target as HTMLButtonElement).style.background = tokens.colors.bg.secondary;
                    (e.target as HTMLButtonElement).style.color = tokens.colors.text.secondary;
                  }
                }}
              >
                ✕
              </button>
            </div>
          ))
        )}
      </div>

      {/* Stats */}
      {!compact && queueState.tracks.length > 0 && (
        <div
          style={{
            paddingTop: tokens.spacing.md,
            borderTop: `1px solid ${tokens.colors.border.light}`,
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: tokens.typography.fontSize.xs,
            color: tokens.colors.text.tertiary,
          }}
        >
          <span>
            {queueState.currentIndex + 1} / {queueState.tracks.length}
          </span>
          <span>Total: {formatTime(totalDuration)}</span>
        </div>
      )}

      {/* Clear Confirmation */}
      {showClearConfirmation && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => setShowClearConfirmation(false)}
        >
          <div
            style={{
              background: tokens.colors.bg.secondary,
              borderRadius: '12px',
              padding: tokens.spacing.lg,
              maxWidth: '400px',
              border: `1px solid ${tokens.colors.border.medium}`,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3
              style={{
                margin: `0 0 ${tokens.spacing.md} 0`,
                fontSize: tokens.typography.fontSize.lg,
                fontWeight: tokens.typography.fontWeight.semibold,
                color: tokens.colors.text.primary,
              }}
            >
              Clear Queue?
            </h3>
            <p
              style={{
                margin: `0 0 ${tokens.spacing.lg} 0`,
                fontSize: tokens.typography.fontSize.sm,
                color: tokens.colors.text.secondary,
              }}
            >
              This will remove all {queueState.tracks.length} tracks from the queue. This action cannot be
              undone.
            </p>
            <div
              style={{
                display: 'flex',
                gap: tokens.spacing.md,
                justifyContent: 'flex-end',
              }}
            >
              <button
                onClick={() => setShowClearConfirmation(false)}
                style={{
                  padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
                  background: tokens.colors.bg.tertiary,
                  border: `1px solid ${tokens.colors.border.light}`,
                  borderRadius: '6px',
                  color: tokens.colors.text.primary,
                  cursor: 'pointer',
                  fontSize: tokens.typography.fontSize.sm,
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleClearQueue}
                style={{
                  padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
                  background: tokens.colors.semantic.error,
                  border: 'none',
                  borderRadius: '6px',
                  color: tokens.colors.text.primary,
                  cursor: 'pointer',
                  fontSize: tokens.typography.fontSize.sm,
                  fontWeight: tokens.typography.fontWeight.semibold,
                }}
              >
                Clear Queue
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default QueueManager;
