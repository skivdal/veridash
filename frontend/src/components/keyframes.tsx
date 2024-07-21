import useBackend, { SourceResponse } from "@/useBackend";

export default function Keyframes({ videoId }: { videoId: string | undefined }) {
  const data = useBackend<SourceResponse>(videoId, "keyframes");

  return (
    <div>Keyframes</div>
  );
}

