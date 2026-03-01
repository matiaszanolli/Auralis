import React from 'react'
import { useCommitId, getVersionString } from '@/hooks/app/useCommitId'
import { tokens } from '@/design-system'
import { spacingSmall, spacingXSmall } from '../library/Styles/Spacing.styles'

/**
 * Debug info component - displays build and commit information
 * Can be toggled via keyboard shortcut (Ctrl+Shift+I in future)
 */
export const DebugInfo: React.FC = () => {
  const [visible, setVisible] = React.useState(false)
  const commitId = useCommitId()
  const versionString = getVersionString()

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + Shift + D to toggle debug info
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'd') {
        e.preventDefault()
        setVisible(prev => !prev)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  if (!visible) return null

  return (
    <div
      style={{
        position: 'fixed',
        bottom: spacingSmall,
        right: spacingSmall,
        backgroundColor: tokens.colors.opacityScale.accent.veryStrong,
        color: tokens.colors.accent.primary,
        padding: `${spacingXSmall} ${spacingSmall}`,
        borderRadius: '8px',
        fontFamily: 'monospace',
        fontSize: '12px',
        zIndex: 10000,
        border: `1px solid ${tokens.colors.accent.primary}`,
        maxWidth: '300px',
      }}
    >
      <div style={{ marginBottom: spacingXSmall, fontWeight: 'bold' }}>🎵 Auralis Debug</div>
      <div>Version: {versionString}</div>
      <div>Commit: {commitId}</div>
      <div>Mode: {import.meta.env.MODE}</div>
      <div style={{ marginTop: spacingXSmall, fontSize: '10px', opacity: 0.7 }}>
        Press Ctrl+Shift+D to toggle
      </div>
    </div>
  )
}

export default DebugInfo
