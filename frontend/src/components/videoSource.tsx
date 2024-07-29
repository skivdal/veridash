import { useState, useEffect } from "react";
import useBackend, { SourceResponse } from "@/useBackend";

export default function VideoSource({ videoId, onFinishedUpload: handleFinishedUpload }:
  { videoId: string | undefined, onFinishedUpload: (videoId?: string, error?: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const data = useBackend<SourceResponse>(videoId, "source", file?.name);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFile(e.target.files[0]);
    }
  };

  useEffect(() => {
    if (!data)
      return;

    (async () => {
      const res = await fetch((data as SourceResponse).uploadUrl, {
        method: "PUT",
        body: file,
        headers: {
          'Content-Type': file!.type,
        },
      });

      if (res.ok) {
        handleFinishedUpload(data!.videoId, undefined);
      } else {
        handleFinishedUpload(undefined, await res.text());
      }
    })();
  }, [data]);

  return (
    <>
      <div>Source</div>
      <div>
        <label htmlFor="file" className="sr-only">
          Choose a file
        </label>
        <input id="file" type="file" onChange={handleFileChange} />
      </div>
    </>
  );
}

