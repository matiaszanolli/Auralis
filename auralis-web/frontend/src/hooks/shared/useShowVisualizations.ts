import { useEffect, useState } from 'react';
import { getSettings, SETTINGS_CHANGED_EVENT, type UserSettings } from '@/services/settingsService';

/**
 * The "Show visualizations" setting, for components outside the Settings dialog (#5676).
 *
 * Settings are fetched only inside the dialog, so the ambient background had nothing to read the
 * switch from and it persisted a value that changed nothing. This reads it once at mount and then
 * follows the settingsService's change event. It defaults to true until the first answer arrives,
 * and when the backend cannot be reached.
 */
export function useShowVisualizations(): boolean {
  const [show, setShow] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getSettings()
      .then((settings) => {
        if (!cancelled) setShow(settings.show_visualizations !== false);
      })
      .catch(() => {
        /* keep the default: the background is decorative */
      });

    const onChanged = (event: Event) => {
      const settings = (event as CustomEvent<UserSettings>).detail;
      setShow(settings.show_visualizations !== false);
    };
    window.addEventListener(SETTINGS_CHANGED_EVENT, onChanged);
    return () => {
      cancelled = true;
      window.removeEventListener(SETTINGS_CHANGED_EVENT, onChanged);
    };
  }, []);

  return show;
}
