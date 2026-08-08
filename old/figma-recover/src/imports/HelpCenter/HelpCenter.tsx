import svgPaths from "./svg-y4l073yu2w";
import imgSkjermbilde20260427Kl1359111 from "./c3fe4d2a48528e574f07f495bfc686f85aadc3ae.png";
import imgImage18 from "./39bfdbc777e10833b7bfacaac17b1b39d1d7df90.png";

function QuillHamburger() {
  return (
    <div className="absolute left-[calc(88.89%+74.5px)] size-[32px] top-[50.74px]" data-name="quill:hamburger">
      <svg className="absolute block inset-0 size-full" fill="none" preserveAspectRatio="none" viewBox="0 0 32 32">
        <g id="quill:hamburger">
          <path d="M5 8H27M5 16H27M5 24H27" id="Vector" stroke="var(--stroke-0, black)" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
        </g>
      </svg>
    </div>
  );
}

function MaterialSymbolsHelpOutlineRounded() {
  return (
    <div className="absolute left-[calc(88.89%+28.5px)] size-[32px] top-[50.74px]" data-name="material-symbols:help-outline-rounded">
      <svg className="absolute block inset-0 size-full" fill="none" preserveAspectRatio="none" viewBox="0 0 32 32">
        <g id="material-symbols:help-outline-rounded">
          <path d={svgPaths.p2a930080} fill="var(--fill-0, black)" id="Vector" />
        </g>
      </svg>
    </div>
  );
}

function Group1() {
  return (
    <div className="absolute contents left-[calc(88.89%+28.5px)] top-[50.74px]">
      <QuillHamburger />
      <MaterialSymbolsHelpOutlineRounded />
    </div>
  );
}

function Group() {
  return (
    <div className="absolute inset-[8.33%]" data-name="Group">
      <div className="absolute inset-[-1.79%]">
        <svg className="block size-full" fill="none" preserveAspectRatio="none" viewBox="0 0 57.8333 57.8333">
          <g id="Group">
            <path d={svgPaths.p3102b700} fill="var(--fill-0, #6EAAF6)" id="Vector" stroke="var(--stroke-0, black)" strokeLinejoin="round" strokeWidth="2" />
            <path d={svgPaths.p12559f00} fill="var(--fill-0, #FFF9F9)" id="Vector_2" stroke="var(--stroke-0, black)" strokeLinejoin="round" strokeWidth="2" />
          </g>
        </svg>
      </div>
    </div>
  );
}

function IconParkOutlinePlay() {
  return (
    <div className="absolute left-[555px] overflow-clip size-[67px] top-[407px]" data-name="icon-park-outline:play">
      <Group />
    </div>
  );
}

function Group2() {
  return (
    <div className="relative my-8 mx-auto" style={{ width: '532px', height: '299px' }}>
      <div className="relative h-full w-full" data-name="image 18">
        <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none size-full rounded-lg" src={imgImage18} />
      </div>
      <div className="absolute left-[233px] overflow-clip size-[67px] top-[116px]">
        <Group />
      </div>
    </div>
  );
}

function Frame() {
  return (
    <div className="-translate-x-1/2 absolute left-1/2 top-[137px] w-[1176px] px-8">
      <div className="font-['Inter:Regular',sans-serif] font-normal leading-[1.6] not-italic text-black pb-8">
        <p className="font-['Inter:Bold',sans-serif] font-bold leading-[normal] mb-6 text-[40px]">Help Center</p>
        <p className="leading-[1.8] mb-8 text-[18px]">VeriDash is a multimedia verification tool that helps users assess whether a video is authentic, misleading, or out of context. It brings together key verification features in one workspace, such as frames, object detection, metadata, transcription, translation, and sharing. VeriDash does not decide whether a video is true or false; instead, it helps users gather and review relevant evidence. The final judgement should always be made by the user.</p>
        <Group2 />
        <p className="font-[‘Inter:Bold’,sans-serif] font-bold leading-[normal] mb-4 mt-12 text-[28px]">Source</p>
        <p className="leading-[1.8] mb-6 text-[18px]">Source is where you upload the video you want to verify. You can either upload a video from your computer or import one by pasting a file URL. Once the video is added, it will appear as a preview in the Source section. This video is then used as the original material for the verification process.</p>
        <p className="font-[‘Inter:Bold’,sans-serif] font-bold leading-[1.8] mb-4 mt-8 text-[28px]">Frames</p>
        <p className="mb-6 text-[18px] leading-[1.8]">
          <span>{`Frames shows the keyframes extracted from your video at a rate of 1 frame per second. This Widget lets you investigate each frame one by one. Use `}</span>
          <span className="font-[‘Inter:Bold’,sans-serif] font-bold not-italic">Stitching</span>
          <span>{` to combine multiple frames into a wider image, which can reveal more visual context and help with geolocation or scene matching. Use `}</span>
          <span className="font-[‘Inter:Bold’,sans-serif] font-bold not-italic">Image Reverse Search</span>
          <span>{` to check whether a frame has appeared online before, which can help identify reused, misleading, or miscaptioned content.`}</span>
        </p>
        <p className="font-[‘Inter:Bold’,sans-serif] font-bold leading-[1.8] mb-4 mt-8 text-[28px]">{`Transcription & Translation`}</p>
        <p className="leading-[1.8] mb-6 text-[18px]">{`Transcription & Translation automatically extracts spoken content from the video and shows it with timestamps. The transcript appears in the original spoken language and is translated into English. Use this tab to check what is being said, compare speech with the video context, and identify claims that may need further verification.`}</p>
        <p className="font-[‘Inter:Bold’,sans-serif] font-bold leading-[1.8] mb-4 mt-8 text-[28px]">Object Detection</p>
        <p className="mb-6 text-[18px] leading-[1.8]">
          <span>{`Object Detection helps identify specific objects that appear in the video frames. Use this widget to focus on details such as signs, vehicles, buildings, products, or other visual clues that may support verification. Use `}</span>
          <span className="font-[‘Inter:Bold’,sans-serif] font-bold not-italic">Image Reverse Search</span>
          <span>{` on detected objects to check whether they appear elsewhere online. This can help confirm locations, identify reused visuals, or find inconsistencies in how the video is presented.`}</span>
        </p>
        <p className="font-[‘Inter:Bold’,sans-serif] font-bold leading-[1.8] mb-4 mt-8 text-[28px]">Metadata</p>
