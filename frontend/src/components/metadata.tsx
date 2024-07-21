import useBackend, { SourceResponse } from "@/useBackend";

export default function Metadata({ videoId }: { videoId: string | undefined }) {
  const data = useBackend<SourceResponse>(videoId, "metadata");

  return (
    <div>Metadata</div>
  );
}

