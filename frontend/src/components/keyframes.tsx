import { useState, useEffect } from "react";
import useBackend, { KeyFramesResponse } from "@/useBackend";
import Stitching from "./stitching";

export default function Keyframes({ videoId, frameNo }: { videoId: string | undefined, frameNo: number | undefined }) {
  const data = useBackend<KeyFramesResponse>(videoId, "keyframes");
  const [frameNumber, setFrameNumber] = useState<number>(1);
  const [stitchingOpen, setStitchingOpen] = useState<boolean>(false);

  useEffect(() => {
    const d = data as KeyFramesResponse;
    if (frameNo && data && frameNo > 0 && frameNo < d.urls.length + 1)
      setFrameNumber(frameNo);
  }, [frameNo]);

  if (!data) {
    const isLoading = !data && videoId;

    return (
      <div>
        <p>Keyframes</p>
        {
          isLoading ? (
            <div className="text-center">
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
              <p>This typically takes 1-2 minutes</p>
            </div>
          ) : ''
        }
      </div>
    );
  }

  const d = data as KeyFramesResponse;
  return (
    <div>
      {(stitchingOpen && videoId) &&
        <Stitching videoId={videoId} isOpen={stitchingOpen} close={() => setStitchingOpen(false)}
          frameLinks={d.urls} startingFrame={frameNumber}
        />
      }

      <p className="mb-2">Keyframes (1 frame per second)</p>

      <div className="h-[28vh] flex items-center justify-center">
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

      <div className="inline-flex justify-between w-full mt-2">
        <div></div>
        <button
          onClick={() => { setStitchingOpen(true) }}
          className="bg-transparent text-grey-700 font-semibold py-2 px-4 border border-grey-500 hover:border-transparent rounded">
          Stitching
        </button>
        <div></div>
      </div>
    </div>
  );
}

