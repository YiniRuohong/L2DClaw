import { useCallback, useEffect, useState } from 'react';
import { useScreenMonitor } from '@\/context\/screen-monitor-context';

interface UseScreenMonitorSettingsProps {
  onSave?: (callback: () => void) => () => void;
  onCancel?: (callback: () => void) => () => void;
}

export function useScreenMonitorSettings({
  onSave,
  onCancel,
}: UseScreenMonitorSettingsProps = {}) {
  const { settings: persistedSettings, setEnabled } = useScreenMonitor();

  const [tempSettings, setTempSettings] = useState({
    enabled: persistedSettings.enabled,
  });

  const [originalSettings, setOriginalSettings] = useState({
    ...persistedSettings,
  });

  useEffect(() => {
    setOriginalSettings(persistedSettings);
    setTempSettings(persistedSettings);
  }, [persistedSettings]);

  const handleEnabledChange = useCallback((checked: boolean) => {
    setTempSettings((prev) => ({
      ...prev,
      enabled: checked,
    }));
  }, []);

  const handleSave = useCallback(() => {
    setEnabled(tempSettings.enabled);
    setOriginalSettings(tempSettings);
  }, [setEnabled, tempSettings]);

  const handleCancel = useCallback(() => {
    setTempSettings(originalSettings);
    setEnabled(originalSettings.enabled);
  }, [originalSettings, setEnabled]);

  useEffect(() => {
    if (!onSave || !onCancel) return;

    const cleanupSave = onSave(handleSave);
    const cleanupCancel = onCancel(handleCancel);

    return () => {
      cleanupSave?.();
      cleanupCancel?.();
    };
  }, [onSave, onCancel, handleSave, handleCancel]);

  return {
    settings: tempSettings,
    handleEnabledChange,
  };
}
