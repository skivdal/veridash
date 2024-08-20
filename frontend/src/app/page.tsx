"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import KeyFrames from "@/components/keyframes";
import Metadata from "@/components/metadata";
import ObjectDetection from "@/components/objectDetection";
import OsmTags from "@/components/osmTags";
import Transcription from "@/components/transcription";
import VideoSource from "@/components/videoSource";

const Map = dynamic(() => import("../components/map"), { ssr: false })

export default function Layout() {
  const [videoId, setVideoId] = useState<string | undefined>(undefined);
  const [scrubTime, setScrubTime] = useState<number | undefined>(undefined);


  return (
    <div className="min-h-screen p-4">
      <h1 className="text-xl font-bold mb-4">Verification Dashboard</h1>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-8 grid grid-rows-2 gap-4">
          <div className="grid grid-cols-8 gap-4">
            <div className="col-span-3 bg-white p-4 h-[45vh]">
              <VideoSource
                videoId={videoId}
                onFinishedUpload={(i, err) => { setVideoId(i); return; }}
                scrubToTime={scrubTime}
                onScrubAccepted={() => { setScrubTime(undefined); }}
              />
            </div>
            <div className="col-span-5 bg-white p-4 h-[45vh]">
              <Map videoId={videoId} />
            </div>
          </div>

          <div className="grid grid-cols-8 gap-4">
            <div className="col-span-3 bg-white p-4 h-[45vh]">
              <KeyFrames videoId={videoId} />
            </div>
            <div className="col-span-2 bg-white p-4 h-[45vh]">
              <Metadata videoId={videoId} />
            </div>
            <div className="col-span-3 bg-white p-4 h-[45vh]">
              <Transcription
                videoId={videoId}
                onScrub={(x) => { setScrubTime(x); }}
              />
            </div>
          </div>
        </div>

        <div className="col-span-4 flex flex-col gap-4">
          <div className="bg-white p-4 h-[60vh]">
            <ObjectDetection videoId={videoId} />
          </div>
          <div className="bg-white p-4 h-[30vh]">
            <OsmTags videoId={videoId} />
          </div>
        </div>
      </div>
    </div>
  );
}

