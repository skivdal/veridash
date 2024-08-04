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
  downloadUrl: string;
}

export interface MetadataResponse extends BackendMessage {
  streams: Object;
  format: Object;
}

export interface TranscriptionResponse extends BackendMessage {
  transcription: {
    text: string;
    segments: Segment[];
    // ISO 639 language code
    language: string;
  };
}

interface Segment {
  id: number;
  seek: number;

  start: number;
  end: number;

  text: string;
  text_en?: string; // present if the language is not english

  temperature: number;
  avg_logprob: number;
  compression_ratio: number;
  no_speech_prob: number;
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

