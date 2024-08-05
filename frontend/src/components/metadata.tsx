import { JsonToTable } from "react-json-to-table";
import useBackend, { MetadataResponse } from "@/useBackend";

export default function Metadata({ videoId }: { videoId: string | undefined }) {
  const data = useBackend<MetadataResponse>(videoId, "metadata");

  return (
    <div className="h-full overflow-auto hover:overflow-scroll">
      <p className="mb-2">Metadata</p>
      <div className="text-xs">
        {data && (data as MetadataResponse)?.format ?
          <JsonToTable json={(data as MetadataResponse).format} />
          : ''}
      </div>
    </div>
  );
}

