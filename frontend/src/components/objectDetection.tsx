import useBackend, { SourceResponse } from "@/useBackend";

export default function ObjectDetection({ videoId }: { videoId: string | undefined }) {
  const data = useBackend<SourceResponse>(videoId, "objectdetection");

  return (
    <div>Object Detection</div>
  );
}

