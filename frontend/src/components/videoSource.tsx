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
  const [loading, setLoading] = useState<boolean>(false);

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

    setLoading(true);
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

      setLoading(false);
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
          {
            loading ? (
              <div className="inline-flex justify-between w-full">
                <div></div>
                <div role="status" className="mt-4">
                  <svg aria-hidden="true" className="w-8 h-8 text-gray-200 animate-spin dark:text-gray-600 fill-blue-600" viewBox="0 0 100 101" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z" fill="currentColor" />
                    <path d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z" fill="currentFill" />
                  </svg>
                  <span className="sr-only">Loading...</span>
                </div>
                <div></div>
              </div>
            ) : ''
          }
        </>
      )}
    </div>
  );
}

