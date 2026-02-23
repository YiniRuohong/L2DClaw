import {
  createContext,
  useCallback,
  useContext,
  useMemo,
} from 'react';
import { useLocalStorage } from '@/hooks/utils/use-local-storage';

interface ScreenMonitorSettings {
  enabled: boolean;
}

interface ScreenMonitorContextType {
  settings: ScreenMonitorSettings;
  setEnabled: (enabled: boolean) => void;
}

const DEFAULT_SETTINGS: ScreenMonitorSettings = {
  enabled: false,
};

export const ScreenMonitorContext = createContext<ScreenMonitorContextType | null>(null);

export function ScreenMonitorProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useLocalStorage<ScreenMonitorSettings>(
    'screenMonitorSettings',
    DEFAULT_SETTINGS,
  );

  const setEnabled = useCallback((enabled: boolean) => {
    setSettings((prev: ScreenMonitorSettings) => ({
      ...prev,
      enabled,
    }));
  }, [setSettings]);

  const contextValue = useMemo(() => ({
    settings,
    setEnabled,
  }), [settings, setEnabled]);

  return (
    <ScreenMonitorContext.Provider value={contextValue}>
      {children}
    </ScreenMonitorContext.Provider>
  );
}

export function useScreenMonitor() {
  const context = useContext(ScreenMonitorContext);

  if (!context) {
    throw new Error('useScreenMonitor must be used within a ScreenMonitorProvider');
  }

  return context;
}
