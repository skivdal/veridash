import useBackend, { SourceResponse } from "@/useBackend";

export default function VideoSource({ videoId, onFinishedUpload: handleFinishedUpload }:
  { videoId: string | undefined, onFinishedUpload: (videoId: string, error: string) => void }) {
  const data = useBackend<SourceResponse>(videoId, "source");

  return (
    <div>Source</div>
  );
}

