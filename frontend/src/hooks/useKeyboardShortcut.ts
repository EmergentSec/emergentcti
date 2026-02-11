import { useEffect, useCallback } from 'react';

interface KeyboardShortcutOptions {
  meta?: boolean;
  ctrl?: boolean;
}

export function useKeyboardShortcut(
  key: string,
  callback: () => void,
  options?: KeyboardShortcutOptions
) {
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      // Don't trigger when typing in form elements
      const target = event.target as HTMLElement;
      const tagName = target.tagName.toLowerCase();
      if (
        tagName === 'input' ||
        tagName === 'textarea' ||
        tagName === 'select' ||
        target.isContentEditable
      ) {
        return;
      }

      const keyMatch = event.key.toLowerCase() === key.toLowerCase();
      if (!keyMatch) return;

      // Check modifier requirements
      if (options?.meta && !event.metaKey) return;
      if (options?.ctrl && !event.ctrlKey) return;

      event.preventDefault();
      callback();
    },
    [key, callback, options?.meta, options?.ctrl]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}

/**
 * Hook specifically for Cmd+K / Ctrl+K that works even in input fields.
 * This is needed because the command palette shortcut should always work.
 */
export function useGlobalKeyboardShortcut(
  key: string,
  callback: () => void,
  options?: KeyboardShortcutOptions
) {
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      const keyMatch = event.key.toLowerCase() === key.toLowerCase();
      if (!keyMatch) return;

      if (options?.meta && !event.metaKey) return;
      if (options?.ctrl && !event.ctrlKey) return;

      event.preventDefault();
      callback();
    },
    [key, callback, options?.meta, options?.ctrl]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}
