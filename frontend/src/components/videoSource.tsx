import { useState, useEffect, useRef } from "react";
import useBackend, { SourceResponse } from "@/useBackend";

export default function VideoSource({
  videoId, onFinishedUpload: handleFinishedUpload,
  scrubToTime, onScrubAccepted: handleScrubAccepted,
}: {
  videoId: string | undefined,
  onFinishedUpload: (videoId?: string, error?: string) => void,
  scrubToTime: number | undefined,
  onScrubAccepted: () => void;
}) {
  const [file, setFile] = useState<[File, string] | null>(null);
  const data = useBackend<SourceResponse>(undefined, "source", file ? `${file[0].name}:${file[1]}` : undefined);
  const videoElement = useRef<HTMLVideoElement>();

  // https://gist.github.com/GaspardP/fffdd54f563f67be8944
  function hex(buffer: ArrayBuffer) {
    var digest = ''
    var view = new DataView(buffer)
    for (var i = 0; i < view.byteLength; i += 4) {
      // We use getUint32 to reduce the number of iterations (notice the `i += 4`)
      var value = view.getUint32(i)
      // toString(16) will transform the integer into the corresponding hex string
      // but will remove any initial "0"
      var stringValue = value.toString(16)
      // One Uint32 element is 4 bytes or 8 hex chars (it would also work with 4
      // chars for Uint16 and 2 chars for Uint8)
      var padding = '00000000'
      var paddedValue = (padding + stringValue).slice(-padding.length)
      digest += paddedValue
    }

    return digest
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      let hash = "";
      try {
        hash = hex(await window.crypto.subtle.digest("SHA-256", await e.target.files[0].arrayBuffer()));
      } catch { }

      setFile([e.target.files[0], hash]);
    }
  };

  useEffect(() => {
    if (!data)
      return;

    (async () => {
      const res = await fetch((data as SourceResponse).uploadUrl, {
        method: "PUT",
        body: file![0],
        headers: {
          'Content-Type': file![0].type,
        },
      });

      if (res.ok) {
        handleFinishedUpload(data!.videoId, undefined);
      } else {
        handleFinishedUpload(undefined, await res.text());
      }
    })();
  }, [data]);

  useEffect(() => {
    if (videoElement.current && scrubToTime != undefined) {
      videoElement.current.currentTime = scrubToTime;
      handleScrubAccepted();
    }
  }, [scrubToTime])

  return (
    <div className="h-full w-full">
      <p className="mb-2">Source</p>

      {videoId && (data as SourceResponse)?.downloadUrl ? (
        /* NOTE: setting height like this a hack to prevent overflow,
         * should be h-full and some flexbox system to make the box the correct size, respecting the header... */
        <video ref={videoElement} controls className="h-[40vh] w-full object-contain">
          <source src={(data as SourceResponse)?.downloadUrl} />
        </video>
      ) : (
        <>
          <label htmlFor="file" className="sr-only">
            Choose a file
          </label>
          <input id="file" type="file" onChange={handleFileChange} />
        </>
      )}
    </div>
  );
}

