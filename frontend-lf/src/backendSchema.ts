import { co, z } from "jazz-tools";

export const BackendProgress = co.map({
  messageType: z.literal(["progress"]),
  progress: z.number(),
});

export const BackendError = co.map({
  messageType: z.literal(["error"]),
  error: z.string(),
});

export const SourceResponse = co.map({
  moduleType: z.literal(["source"]),
  uploadUrl: z.string(),
  downloadUrl: z.string(),
});

export const MetadataResponse = co.map({
  moduleType: z.literal(["metadata"]),
  streams: z.object(),
  format: z.object(),
});

const Segment = co.map({
  id: z.number(),
  seek: z.number(),
  start: z.number(),
  end: z.number(),
  text: z.string(),
  text_en: z.string().optional(),
  temperature: z.number(),
  avg_logprob: z.number(),
  compression_ratio: z.number(),
  no_speech_prob: z.number(),
});

export const TranscriptionResponse = co.map({
  moduleType: z.literal(["transcription"]),
  transcription: co.map({
    text: z.string(),
    language: z.string(),
    segments: co.list(Segment),
  }),
});

export const MapResponse = co.map({
  moduleType: z.literal(["map"]),
  latlng: z.tuple([z.number(), z.number()]).optional(),
});

export const KeyFramesResponse = co.map({
  moduleType: z.literal(["keyframes"]),
  urls: z.array(z.string()),
});

export const ObjDetectResponse = co.map({
  moduleType: z.literal(["object-detection"]),
  urls: z.array(z.string()),
  keyFrameNumbers: z.array(z.number()),
});

export const StitchingResponse = co.map({
  moduleType: z.literal(["stitching"]),
  url: z.string(),
  sourceKeyFrames: z.array(z.number()),
});

export const BackendData = co.map({
  messageType: z.literal(["data"]),
  data: co.discriminatedUnion("moduleType", [
    SourceResponse,
    MetadataResponse,
    TranscriptionResponse,
    MapResponse,
    KeyFramesResponse,
    ObjDetectResponse,
    StitchingResponse,
  ])
});

export const BackendMessage = co.map({
  videoId: z.string().optional(),
  filename: z.string().optional(),
  imageId: z.string().optional(),
  sourceKeyFrames: z.array(z.number()).optional(),
  timestamp: z.date(),

  progressOrData: co.discriminatedUnion("messageType", [
    BackendProgress,
    BackendError,
    BackendData,
  ]),
});

