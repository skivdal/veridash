interface BackendMessage {
  messageType: string;
  videoId?: string;
  filename?: string;
  imageId?: string;
  sourceKeyFrames?: number[];
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

export interface MapResponse extends BackendMessage {
  latlng: number[] | null;
}

export interface KeyFramesResponse extends BackendMessage {
  urls: string[];
}

export interface ObjDetectResponse extends BackendMessage {
  urls: string[];
  keyFrameNumbers: number[];
}

export interface StitchingResponse extends BackendMessage {
  url: string;
  sourceKeyFrames: number[];
}

