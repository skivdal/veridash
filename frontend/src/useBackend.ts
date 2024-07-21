import config from "@/config";
import { useState, useEffect } from "react";
import useWebSocket from "react-use-websocket";

interface BackendMessage {
  messageType: string;
  videoId: string;
}

export interface BackendProgress extends BackendMessage {
  progress: number;
}

export interface BackendError extends BackendMessage {
  error: string;
}

export interface SourceResponse extends BackendMessage { }

export default function useBackend<T extends BackendMessage>(videoId: string | undefined, messageType: string):
  T | BackendProgress | BackendError | undefined {

  const [msg, setMsg] = useState<T | BackendProgress | BackendError | undefined>(undefined);
  const { lastJsonMessage, sendJsonMessage } = useWebSocket(config.websocketUrl, { share: true });

  useEffect(() => {
    if (videoId)
      sendJsonMessage<BackendMessage>({ messageType, videoId });
  }, [sendJsonMessage, messageType, videoId]);

  useEffect(() => {
    if (lastJsonMessage
      && (lastJsonMessage as BackendMessage).messageType === messageType
      && (lastJsonMessage as BackendMessage).videoId === videoId) {
      setMsg(lastJsonMessage as (T | BackendProgress | BackendError));
    }
  }, [lastJsonMessage, messageType]);

  return msg;
}

