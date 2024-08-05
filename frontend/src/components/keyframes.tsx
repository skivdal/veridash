import { useState } from "react";
import useBackend, { KeyFramesResponse } from "@/useBackend";

export default function Keyframes({ videoId }: { videoId: string | undefined }) {
  const data = useBackend<KeyFramesResponse>(videoId, "keyframes");
  const [frameNumber, setFrameNumber] = useState<number>(1);

  if (!data) {
    return <div>Keyframes</div>;
  }

  const d = data as KeyFramesResponse;
  return (
    <div>
      <p className="mb-2">Keyframes (1 frame per second)</p>

      <div className="h-[33vh] flex items-center justify-center">
        <img
          src={d.urls[frameNumber - 1]}
          className="max-h-full max-w-full object-contain">
        </img>
      </div>

      <div className="inline-flex justify-between w-full mt-2">
        <button
          onClick={() => { if (frameNumber > 1) setFrameNumber(frameNumber - 1); }}
          className="bg-transparent text-grey-700 font-semibold py-2 px-4 border border-grey-500 hover:border-transparent rounded">
          Previous
        </button>

        <span className="py-2 px-4">{frameNumber} / {d.urls.length}</span>

        <button
          onClick={() => { if (frameNumber < d.urls.length) setFrameNumber(frameNumber + 1); }}
          className="bg-transparent text-grey-700 font-semibold py-2 px-4 border border-grey-500 hover:border-transparent rounded">
          Next
        </button>
      </div>
    </div>
  );
}

