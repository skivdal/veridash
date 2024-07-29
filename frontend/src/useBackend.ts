import config from "@/config";
import { useState, useEffect } from "react";
import useWebSocket from "react-use-websocket";

interface BackendMessage {
  messageType: string;
  videoId?: string;
  filename?: string;
  imageId?: string;
}

export interface BackendProgress extends BackendMessage {
  progress: number;
}

export interface BackendError extends BackendMessage {
  error: string;
}

export interface SourceResponse extends BackendMessage {
  uploadUrl: string;
}

export default function useBackend<T extends BackendMessage>(videoId: string | undefined, messageType: string,
  filename?: string, imageId?: string): T | BackendProgress | BackendError | undefined {

  const [msg, setMsg] = useState<T | BackendProgress | BackendError | undefined>(undefined);
  const { lastJsonMessage, sendJsonMessage } = useWebSocket(config.websocketUrl, { share: true });

  useEffect(() => {
    if (videoId || filename) {
      const msg: BackendMessage = { messageType, videoId };
      if (filename)
        msg.filename = filename;
      if (imageId)
        msg.imageId = imageId;

      sendJsonMessage<BackendMessage>(msg);
    }
  }, [sendJsonMessage, messageType, videoId, filename, imageId]);

  useEffect(() => {
    if (lastJsonMessage
      && (lastJsonMessage as BackendMessage).messageType === messageType
      && ((lastJsonMessage as BackendMessage).videoId === videoId || !videoId)) {
      setMsg(lastJsonMessage as (T | BackendProgress | BackendError));
    }
  }, [lastJsonMessage, messageType]);

  return msg;
}

