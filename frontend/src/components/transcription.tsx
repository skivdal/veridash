import useBackend, { SourceResponse } from "@/useBackend";

export default function Transcription({ videoId }: { videoId: string | undefined }) {
  const data = useBackend<SourceResponse>(videoId, "transcription");

  return (
    <div>Transcription/translation</div>
  );
}

