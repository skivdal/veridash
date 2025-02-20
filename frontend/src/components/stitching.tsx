import { useState, useEffect } from "react";
import { Dialog, DialogBackdrop, DialogPanel, DialogTitle } from "@headlessui/react";
import useBackend, { StitchingResponse } from "@/useBackend";

export default function Stitching({ videoId, isOpen, close, frameLinks, startingFrame }:
  { videoId: string, isOpen: boolean, close: () => void, frameLinks: string[], startingFrame: number }) {
  // One-based indexing, inclusive at both sides
  const [startFrame, setStartFrame] = useState(startingFrame);
  const [endFrame, setEndFrame] = useState(Math.min(startingFrame + 10, frameLinks.length));
  const [confirmedFrameRange, setConfirmedFrameRange] = useState<number[]>([]);

  const data = useBackend<StitchingResponse>(videoId, "stitching", undefined, undefined, confirmedFrameRange);

  useEffect(() => {
    if (startFrame <= 0) {
      setStartFrame(1);
    }

    if (endFrame > frameLinks.length) {
      setEndFrame(frameLinks.length);
    }

    if (startFrame > endFrame) {
      const pEnd = endFrame;
      setEndFrame(startFrame);
      setStartFrame(pEnd);
    }
  }, [startFrame, endFrame]);

  const handleStitch = () => {
    const r = [];
    for (let i = startFrame; i <= endFrame; ++i) {
      r.push(i);
    }

    setConfirmedFrameRange(r);
  }

  const isLoading = !data && confirmedFrameRange.length != 0;
  const d = data as StitchingResponse;
  const hasData = d?.url ? true : false;

  return (
    <Dialog open={isOpen} onClose={close} className="relative z-[1001]">
      <DialogBackdrop
        transition
        className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity data-[closed]:opacity-0 data-[enter]:duration-300 data-[leave]:duration-200 data-[enter]:ease-out data-[leave]:ease-in"
      />

      <div className="fixed inset-0 z-[1001] w-screen overflow-y-auto">
        <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
          <DialogPanel
            transition
            className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all data-[closed]:translate-y-4 data-[closed]:opacity-0 data-[enter]:duration-300 data-[leave]:duration-200 data-[enter]:ease-out data-[leave]:ease-in sm:my-8 sm:w-full sm:max-w-fit sm:p-6 data-[closed]:sm:translate-y-0 data-[closed]:sm:scale-95 sm:m-4"
          >
            <div>
              <DialogTitle as="h3" className="text-base text-center font-semibold leading-6 text-gray-900">
                Image stitching
              </DialogTitle>

              {/* This is the inner part */}
              {!isLoading && !hasData &&
                <>
                  <label htmlFor="startFrameInput" className="text-gray-600">Starting frame:</label>
                  <input id="startFrameInput" type="number"
                    className="w-20 ml-2 mr-2"
                    onChange={(e) => setStartFrame(parseInt(e.target.value))}
                    value={startFrame.toString()} />

                  <label htmlFor="endFrameInput" className="text-gray-600">Ending frame:</label>
                  <input id="endFrameInput" type="number"
                    className="w-20 ml-2 mr-2"
                    onChange={(e) => setEndFrame(parseInt(e.target.value))}
                    value={endFrame.toString()} />

                  <div className="h-[70vh] overflow-auto hover:overflow-scroll">
                    <div className="mt-3 text-center sm:mt-5">
                      <div className="grid grid-cols-6 gap-4">
                        {frameLinks.slice(startFrame - 1, endFrame).map(u =>
                          <img key={u} src={u}></img>
                        )}
                      </div>
                    </div>
                  </div>
                </>
              }

              {isLoading &&
                <>
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
                </>
              }

              {hasData &&
                <div className="max-h-[50vh] max-w-[50vw] m-4">
                  <p className="mb-2">Resulting Image:</p>
                  <img src={d.url} className="max-h-[80%] max-w-[80%]"></img>
                </div>
              }
            </div>
            <div className="mt-5 sm:mt-6 inline-flex justify-between w-full">
              <button
                onClick={() => close()}
                className="bg-transparent text-grey-700 font-semibold py-2 px-4 border border-grey-500 hover:border-transparent rounded">
                Go back to dashboard
              </button>

              <button
                type="button"
                onClick={handleStitch}
                className="bg-indigo-500 text-white font-semibold py-2 px-4 border border-grey-500 hover:border-transparent rounded"
              >
                Run stitch
              </button>
            </div>
          </DialogPanel>
        </div>
      </div>
    </Dialog>
  )
}

