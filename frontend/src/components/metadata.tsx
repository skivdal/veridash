import useBackend, { MetadataResponse } from "@/useBackend";

export default function Metadata({ videoId }: { videoId: string | undefined }) {
  const data = useBackend<MetadataResponse>(videoId, "metadata");

  return (
    <div className="h-full overflow-auto hover:overflow-scroll">
      <div>Metadata:</div>
      <pre className="text-xs">
        {data ? JSON.stringify((data as MetadataResponse).format, undefined, 2) : ''}
      </pre>
    </div>
  );
}

