import useBackend, { SourceResponse } from "@/useBackend";

export default function OsmTags({ videoId }: { videoId: string | undefined }) {
  const data = useBackend<SourceResponse>(videoId, "osmtags");

  return <div></div>;
}

