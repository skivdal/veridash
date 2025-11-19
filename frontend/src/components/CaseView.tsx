"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import {
  FaVideo,
  FaMicrochip,
  FaFont,
  FaTags,
  FaQuestionCircle,
  FaArchive,
} from "react-icons/fa";
import { BsFileEarmarkTextFill, BsMap, BsListUl } from "react-icons/bs";

import Topbar from "@/components/Topbar";
import TabTopbar from "@/components/TabTopbar";

import VideoSource from "@/components/videoSource";
import KeyFrames from "@/components/keyframes";
import Metadata from "@/components/metadata";
import Transcription from "@/components/transcription";
import ObjectDetection from "@/components/objectDetection";
import OsmTags from "@/components/osmTags";
import useWebSocket from "react-use-websocket";
import config from "@/config";

const Map = dynamic(() => import("@/components/map"), { ssr: false });

const MODULES = [
  { id: "video", label: "Source", icon: <FaVideo /> },
  { id: "keyframes", label: "Frames", icon: <BsListUl /> },
  { id: "object", label: "Object Detection", icon: <FaMicrochip /> },
  { id: "metadata", label: "Metadata", icon: <BsFileEarmarkTextFill /> },
  { id: "transcription", label: "Transcription & Translation", icon: <FaFont /> },
  { id: "map", label: "Map", icon: <BsMap /> },
  { id: "notepad", label: "Notepad", icon: <FaTags /> },
  { id: "archive", label: "Archive", icon: <FaArchive /> },
  { id: "help", label: "Help", icon: <FaQuestionCircle /> },
];

export default function CaseView({ caseId }: { caseId: string }) {
  const [activeModule, setActiveModule] = useState("video");
  const [videoId, setVideoId] = useState<string | undefined>(undefined);
  const [scrubTime, setScrubTime] = useState<number | undefined>(undefined);
  const [keyFrameNumber, setKeyFrameNumber] = useState<number | undefined>(undefined);

  // Hack to ensure the WS stays open when switching between modules
  const _ = useWebSocket(config.websocketUrl, { share: true });

  return (
    <div className="flex flex-col h-screen">
      {/* Top bars */}
      
      <Topbar currentCaseId={caseId} />
      <TabTopbar
        currentCaseId={caseId}
        activeModule={activeModule}
        onChangeModule={setActiveModule}
      />

      {/* Main screen: sidebar + canvas */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-20 sm:w-24 bg-white border-r flex flex-col items-center py-6 gap-4">
          {MODULES.map((mod) => (
            <button
              key={mod.id}
              onClick={() => setActiveModule(mod.id)}
              className={`flex flex-col items-center text-[0.65rem] sm:text-xs font-medium focus:outline-none ${
                activeModule === mod.id
                  ? "text-blue-600"
                  : "text-gray-400 hover:text-gray-600"
              }`}
            >
              <div className="text-xl mb-1">{mod.icon}</div>
              <span className="text-center leading-tight">{mod.label}</span>
            </button>
          ))}
        </aside>

        {/* Canvas with dot grid */}
        <main
          className="
            flex-1 overflow-auto p-8
            bg-gray-50
            [background-image:radial-gradient(#d1d5db_1px,transparent_1px)]
            [background-size:16px_16px]
            [background-position:0_0]
          "
        >
          <div className="pl-2">
            {/* Tabs/Sidebar controlled modules */}
            {activeModule === "video" && (
              <VideoSource
                videoId={videoId}
                onFinishedUpload={(id) => setVideoId(id)}
                scrubToTime={scrubTime}
                onScrubAccepted={() => setScrubTime(undefined)}
              />
            )}

            {activeModule === "map" && <Map videoId={videoId} />}

            {activeModule === "keyframes" && (
              <KeyFrames videoId={videoId} frameNo={keyFrameNumber} />
            )}

            {activeModule === "metadata" && <Metadata videoId={videoId} />}

            {activeModule === "transcription" && (
              <Transcription videoId={videoId} onScrub={(t) => setScrubTime(t)} />
            )}

            {activeModule === "object" && (
              <ObjectDetection
                videoId={videoId}
                onUpdateKeyFrame={(i: number) => setKeyFrameNumber(i)}
              />
            )}

            {activeModule === "tags" && <OsmTags videoId={videoId} />}

            {activeModule === "notepad" && (
              <div className="text-gray-500 italic mt-20">Notes coming soon…</div>
            )}

            {activeModule === "stitching" && (
              <div className="text-gray-500 italic mt-20">Stitching coming soon…</div>
            )}

            {(activeModule === "archive" || activeModule === "help") && (
              <div className="text-gray-500 italic mt-20">Coming soon…</div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
