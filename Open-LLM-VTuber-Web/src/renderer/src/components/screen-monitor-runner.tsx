import { useEffect, useRef } from 'react';
import { useScreenMonitor } from '@/context/screen-monitor-context';
import { useScreenCaptureContext } from '@/context/screen-capture-context';
import { useMediaCapture } from '@/hooks/utils/use-media-capture';
import { useWebSocket } from '@/context/websocket-context';
import { useAiState, AiStateEnum } from '@/context/ai-state-context';

const MONITOR_INTERVAL_MS = 5000;
const SCREEN_MONITOR_PROMPT = '请简短描述我当前屏幕上正在显示的内容，用陪伴/吐槽语气。';

function ScreenMonitorRunner(): null {
  const { settings } = useScreenMonitor();
  const { stream, startCapture, stopCapture } = useScreenCaptureContext();
  const { captureAllMedia } = useMediaCapture();
  const { sendMessage, wsState } = useWebSocket();
  const { aiState } = useAiState();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedByMonitorRef = useRef(false);
  const isSendingRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    const clearTimer = () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };

    const stopOwnedCapture = () => {
      if (startedByMonitorRef.current) {
        stopCapture();
        startedByMonitorRef.current = false;
      }
    };

    const ensureScreenStream = async () => {
      if (stream) return true;
      try {
        await startCapture();
        startedByMonitorRef.current = true;
        return true;
      } catch (error) {
        console.error('Failed to start screen capture for screen monitor:', error);
        return false;
      }
    };

    const startMonitor = async () => {
      const ready = await ensureScreenStream();
      if (!ready || cancelled) return;

      intervalRef.current = setInterval(async () => {
        if (isSendingRef.current) return;
        if (wsState !== 'OPEN') return;
        if (aiState !== AiStateEnum.IDLE) return;

        isSendingRef.current = true;
        try {
          const images = await captureAllMedia();
          if (!images.length) return;

          const taggedImages = images.map((image: { source: string }) =>
            image.source === 'screen'
              ? { ...image, category: 'screen-monitor' as const }
              : image
          );

          sendMessage({
            type: 'text-input',
            text: SCREEN_MONITOR_PROMPT,
            images: taggedImages,
          });
        } finally {
          isSendingRef.current = false;
        }
      }, MONITOR_INTERVAL_MS);
    };

    if (settings.enabled) {
      startMonitor();
    } else {
      clearTimer();
      stopOwnedCapture();
    }

    return () => {
      cancelled = true;
      clearTimer();
      stopOwnedCapture();
    };
  }, [
    settings.enabled,
    stream,
    startCapture,
    stopCapture,
    captureAllMedia,
    sendMessage,
    wsState,
    aiState,
  ]);

  return null;
}

export default ScreenMonitorRunner;
