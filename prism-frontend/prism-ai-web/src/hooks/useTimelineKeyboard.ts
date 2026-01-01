/**
 * Timeline Keyboard Shortcuts Hook
 * 
 * Handles keyboard shortcuts for timeline navigation and actions
 */

import { useEffect } from 'react';

export interface TimelineKeyboardShortcuts {
  onNavigateLeft?: () => void;
  onNavigateRight?: () => void;
  onTogglePause?: () => void;
  onUndo?: () => void;
  onRedo?: () => void;
  onViewDiff?: () => void;
  onClosePanel?: () => void;
  onSearch?: () => void;
}

export function useTimelineKeyboard(shortcuts: TimelineKeyboardShortcuts, enabled: boolean = true) {
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Check for modifier keys
      const isCmdOrCtrl = e.metaKey || e.ctrlKey;
      const isShift = e.shiftKey;

      // Left/Right arrow keys - Navigate timeline
      if (e.key === 'ArrowLeft' && !isCmdOrCtrl) {
        e.preventDefault();
        shortcuts.onNavigateLeft?.();
        return;
      }
      
      if (e.key === 'ArrowRight' && !isCmdOrCtrl) {
        e.preventDefault();
        shortcuts.onNavigateRight?.();
        return;
      }

      // Space - Play/Pause active build
      if (e.key === ' ' && !isCmdOrCtrl) {
        e.preventDefault();
        shortcuts.onTogglePause?.();
        return;
      }

      // U - Undo last change
      if (e.key === 'u' && !isCmdOrCtrl) {
        e.preventDefault();
        shortcuts.onUndo?.();
        return;
      }

      // R - Redo
      if (e.key === 'r' && !isCmdOrCtrl) {
        e.preventDefault();
        shortcuts.onRedo?.();
        return;
      }

      // D - View diff
      if (e.key === 'd' && !isCmdOrCtrl) {
        e.preventDefault();
        shortcuts.onViewDiff?.();
        return;
      }

      // Escape - Close detail panel
      if (e.key === 'Escape') {
        e.preventDefault();
        shortcuts.onClosePanel?.();
        return;
      }

      // Cmd/Ctrl + Z - Undo to selected point (platform-specific)
      if (isCmdOrCtrl && e.key === 'z' && !isShift) {
        // Note: This might conflict with editor undo
        // Only handle if timeline is focused
        if (document.activeElement?.closest('.timeline-container')) {
          e.preventDefault();
          shortcuts.onUndo?.();
        }
        return;
      }

      // Cmd/Ctrl + F - Search timeline
      if (isCmdOrCtrl && e.key === 'f') {
        // Note: This might conflict with browser search
        // Only handle if timeline is focused
        if (document.activeElement?.closest('.timeline-container')) {
          e.preventDefault();
          shortcuts.onSearch?.();
        }
        return;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts, enabled]);
}
