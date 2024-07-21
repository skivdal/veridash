import KeyFrames from "@/components/keyframes";
import Map from "@/components/map";
import Metadata from "@/components/metadata";
import ObjectDetection from "@/components/objectDetection";
import OsmTags from "@/components/osmTags";
import Transcription from "@/components/transcription";
import VideoSource from "@/components/videoSource";

export default function Layout() {
  return (
    <div className="min-h-screen p-4">
      <h1 className="text-xl font-bold mb-4">Verification dashboard</h1>

      <div className="grid grid-cols-12 gap-4 mb-4">
        <div className="col-span-8 grid grid-rows-2 gap-4">
          <div className="grid grid-cols-8 gap-4">
            <div className="col-span-3 bg-white p-4 h-[45vh]">
              <VideoSource />
            </div>
            <div className="col-span-5 bg-white p-4 h-[45vh]">
              <Map />
            </div>
          </div>

          <div className="grid grid-cols-8 gap-4">
            <div className="col-span-3 bg-white p-4 h-[45vh]">
              <KeyFrames />
            </div>
            <div className="col-span-2 bg-white p-4 h-[45vh]">
              <Metadata />
            </div>
            <div className="col-span-3 bg-white p-4 h-[45vh]">
              <Transcription />
            </div>
          </div>
        </div>

        <div className="col-span-4 flex flex-col gap-4">
          <div className="bg-white p-4 h-[60vh]">
            <ObjectDetection />
          </div>
          <div className="bg-white p-4 h-[30vh]">
            <OsmTags />
          </div>
        </div>
      </div>
    </div>
  );
}

