import useBackend, { SourceResponse } from "@/useBackend";

export default function Map({ videoId }: { videoId: string | undefined }) {
  const data = useBackend<SourceResponse>(videoId, "map");

  return (
    <div>Map</div>
  );
}

