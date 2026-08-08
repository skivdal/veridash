import React, { useState, useEffect } from 'react';
import { Plus, Minus } from 'lucide-react';
import { createPortal } from 'react-dom';
import { DndProvider, useDrag, useDrop } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import svgPaths from '../imports/DenneViBrukerNa/svg-9l405kxn4u';
import logoImage from '../imports/DenneViBrukerNa/c3fe4d2a48528e574f07f495bfc686f85aadc3ae.png';
import HelpCenter from '../imports/HelpCenter/HelpCenter';
import { MetadataExpandedView } from './components/MetadataExpandedView';

type FilterType = 'source' | 'metadata' | 'transcription' | 'frames' | 'map' | 'notes' | 'detection';

interface WidgetConfig {
  id: FilterType;
  rowSpan: number;
}

interface DraggableWidgetProps {
  id: FilterType;
  index: number;
  rowSpan: number;
  title: string;
  isYellow?: boolean;
  customizeMode: boolean;
  moveWidget: (dragIndex: number, hoverIndex: number) => void;
  onExpand?: () => void;
  onHelp?: (rect: DOMRect) => void;
  onSound?: () => void;
  children?: React.ReactNode;
}

function DraggableWidget({ id, index, rowSpan, title, isYellow, customizeMode, moveWidget, onExpand, onHelp, onSound, children }: DraggableWidgetProps) {
  const widgetRef = React.useRef<HTMLDivElement>(null);
  const [{ isDragging }, drag] = useDrag({
    type: 'widget',
    item: { index, id },
    canDrag: customizeMode,
    collect: (monitor) => ({
      isDragging: monitor.isDragging(),
    }),
  });

  const [{ isOver }, drop] = useDrop({
    accept: 'widget',
    collect: (monitor) => ({
      isOver: monitor.isOver({ shallow: true }),
    }),
    hover: (item: { index: number; id: string }, monitor) => {
      if (!customizeMode) return;

      const dragIndex = item.index;
      const hoverIndex = index;

      if (dragIndex === hoverIndex) return;

      // Get the bounding box to make swapping more immediate
      const hoverBoundingRect = monitor.getClientOffset();
      if (!hoverBoundingRect) return;

      // Perform the swap immediately for more responsive feedback
      moveWidget(dragIndex, hoverIndex);
      item.index = hoverIndex;
    },
  });

  const bgColor = isYellow ? 'bg-[#eff6ff]' : 'bg-white';
  const cursorClass = customizeMode ? 'cursor-move' : 'cursor-pointer';
  const borderClass = isOver && customizeMode ? 'ring-2 ring-[#0065f4]' : '';
  const shadowClass = 'shadow-md hover:shadow-[0_20px_50px_rgba(0,0,0,0.25)] transition-shadow duration-300';

  const handleClick = () => {
    if (!customizeMode && onExpand) {
      onExpand();
    }
  };

  const handleHelpClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onHelp && widgetRef.current) {
      const rect = widgetRef.current.getBoundingClientRect();
      onHelp(rect);
    }
  };

  const handleSoundClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onSound) {
      onSound();
    }
  };

  return (
    <div
      ref={(node) => {
        widgetRef.current = node;
        drag(drop(node));
      }}
      onClick={handleClick}
      className={`${bgColor} rounded-[16px] h-full flex flex-col relative group ${shadowClass} ${cursorClass} ${isDragging ? 'opacity-40 scale-[0.98]' : ''} ${borderClass} overflow-hidden transition-opacity`}
    >
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200">
        <h2 className="text-[18px] font-normal text-black whitespace-nowrap" dangerouslySetInnerHTML={{ __html: title }} />
        <div className="flex items-center gap-1">
          {onSound && (
            <button
              onClick={handleSoundClick}
              className="p-1 transition-opacity group/icon"
              aria-label="Play audio"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 260 228">
                <path d="M170.81,78.043l15.653-15.653c14.848,12.299,24.323,30.868,24.323,51.61c0,21.04-9.757,39.836-24.974,52.128l-15.68-15.68c11.291-8.184,18.655-21.469,18.655-36.448C188.786,99.32,181.719,86.262,170.81,78.043z M236,114c0,28.068-12.569,53.253-32.371,70.231l15.584,15.584C242.982,178.82,258,148.133,258,114c0-33.836-14.757-64.286-38.168-85.265L204.257,44.31C223.696,61.28,236,86.229,236,114z M146,2L56.4,66H2v96h54.4l89.6,64V2z" className="fill-[#8C8C8C] group-hover/icon:fill-[#0065f4] transition-colors" />
              </svg>
            </button>
          )}
          <button
            onClick={handleHelpClick}
            className="p-1 transition-opacity group/icon"
            aria-label="Help"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24">
              <path d={svgPaths.p2c3eff80} className="fill-[#8C8C8C] group-hover/icon:fill-[#0065f4] transition-colors" />
            </svg>
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        {children}
      </div>
    </div>
  );
}

function SourceWidget({ videoUrl, setVideoUrl, onFramesExtracted }: { videoUrl: string; setVideoUrl: (url: string) => void; onFramesExtracted: (frames: string[]) => void }) {
  const [urlInput, setUrlInput] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  const extractFrames = async (videoSrc: string) => {
    const video = document.createElement('video');
    video.src = videoSrc;
    video.crossOrigin = 'anonymous';
    video.muted = true;
    video.playsInline = true;

    // Wait for video to load
    await new Promise((resolve) => {
      video.onloadedmetadata = resolve;
      video.load();
    });

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    const duration = video.duration;
    const frameCount = 8;
    const frames: string[] = [];

    for (let i = 0; i < frameCount; i++) {
      const time = (duration / (frameCount + 1)) * (i + 1);

      // Seek to the time
      video.currentTime = time;

      // Wait for seek to complete
      await new Promise((resolve) => {
        video.onseeked = resolve;
      });

      // Draw the frame
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
      frames.push(dataUrl);
    }

    onFramesExtracted(frames);
  };

  const handleFileUpload = async (file: File) => {
    if (file && file.type.startsWith('video/')) {
      const url = URL.createObjectURL(file);
      setVideoUrl(url);

      // Extract frames
      try {
        await extractFrames(url);
      } catch (error) {
        console.error('Error extracting frames:', error);
      }
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileUpload(file);
  };

  const handleUrlImport = async () => {
    if (urlInput.trim()) {
      const url = urlInput.trim();
      setVideoUrl(url);
      setUrlInput('');

      // Extract frames
      try {
        await extractFrames(url);
      } catch (error) {
        console.error('Error extracting frames:', error);
      }
    }
  };

  if (videoUrl) {
    return (
      <div className="h-full w-full p-2" onClick={(e) => e.stopPropagation()}>
        <video
          controls
          className="w-full h-full rounded-lg bg-black"
          src={videoUrl}
        >
          Your browser does not support the video tag.
        </video>
      </div>
    );
  }

  return (
    <div className="h-full w-full p-2 flex flex-col gap-2">
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`flex-1 border-2 border-dashed rounded-lg flex flex-col items-center justify-center gap-2 transition-colors ${
          isDragging ? 'border-[#0065f4] bg-[#deecff]' : 'border-gray-300 bg-gray-50'
        }`}
      >
        <svg className="w-10 h-10 text-[#0065f4]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        <p className="text-xs text-gray-600 text-center px-2">
          Drag & drop your video or{' '}
          <label className="text-[#0065f4] cursor-pointer underline" onClick={(e) => e.stopPropagation()}>
            click to upload
            <input
              type="file"
              accept="video/*"
              onChange={handleFileSelect}
              className="hidden"
            />
          </label>
        </p>
      </div>

      <div className="flex flex-col gap-1" onClick={(e) => e.stopPropagation()}>
        <label className="text-xs font-medium">Import from URL</label>
        <div className="flex gap-1">
          <input
            type="text"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleUrlImport()}
            placeholder="Add file URL"
            className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded outline-none focus:border-[#0065f4]"
          />
          <button
            onClick={handleUrlImport}
            className="px-3 py-1 text-xs bg-[#0065f4] text-white rounded hover:bg-[#0052cc] transition-colors"
          >
            Import
          </button>
        </div>
      </div>
    </div>
  );
}

interface DetectedObject {
  id: string;
  label: string;
  confidence: number;
  frameIndex: number;
  imageData: string;
}

function ObjectDetectionWidget({ frames }: { frames: string[] }) {
  const [currentObjectIndex, setCurrentObjectIndex] = useState(0);
  const widgetRef = React.useRef<HTMLDivElement>(null);
  // Mock detected objects - in real implementation these would be cropped from actual object detection bounding boxes
  // Each object has a zoom and position to simulate cropped object views
  const detectedObjects: (DetectedObject & { zoom: number; positionX: string; positionY: string })[] = frames.length > 0 ? [
    { id: '1', label: 'Firefighter', confidence: 0.96, frameIndex: 0, imageData: frames[0], zoom: 2.2, positionX: '45%', positionY: '40%' },
    { id: '2', label: 'Fire', confidence: 0.94, frameIndex: 1, imageData: frames[1], zoom: 1.8, positionX: '50%', positionY: '60%' },
    { id: '3', label: 'Roof', confidence: 0.88, frameIndex: 2, imageData: frames[2], zoom: 2.4, positionX: '65%', positionY: '30%' },
    { id: '4', label: 'Smoke', confidence: 0.91, frameIndex: 3, imageData: frames[3], zoom: 1.9, positionX: '35%', positionY: '55%' },
    { id: '5', label: 'Fog', confidence: 0.82, frameIndex: 4, imageData: frames[4], zoom: 2.5, positionX: '55%', positionY: '50%' },
    { id: '6', label: 'Hose', confidence: 0.85, frameIndex: 5, imageData: frames[5] || frames[0], zoom: 2.8, positionX: '60%', positionY: '45%' },
    { id: '7', label: 'Flames', confidence: 0.89, frameIndex: 6, imageData: frames[6] || frames[1], zoom: 1.7, positionX: '70%', positionY: '35%' },
  ] : [];

  if (detectedObjects.length === 0) {
    return (
      <div className="p-3 flex items-center justify-center h-full text-gray-400 text-sm">
        No object detection data
      </div>
    );
  }

  const currentObject = detectedObjects[currentObjectIndex];

  const goToPrevious = () => {
    setCurrentObjectIndex((prev) => (prev > 0 ? prev - 1 : detectedObjects.length - 1));
  };

  const goToNext = () => {
    setCurrentObjectIndex((prev) => (prev < detectedObjects.length - 1 ? prev + 1 : 0));
  };



  const handleButtonLeave = () => {
    setHoveredButton(null);
  };

  return (
    <div ref={widgetRef} className="relative h-full w-full overflow-visible">
      <div className="h-full w-full flex flex-col p-2 gap-2">
        {/* Top - Object display (zoomed in on detected object) */}
        <div className="relative flex items-center justify-center bg-black rounded-lg overflow-hidden flex-1">
          <div className="relative w-full h-full overflow-hidden">
            <img
              src={currentObject.imageData}
              alt={currentObject.label}
              className="absolute min-w-full min-h-full object-cover"
              style={{
                transform: `scale(${currentObject.zoom})`,
                transformOrigin: `${currentObject.positionX} ${currentObject.positionY}`,
              }}
            />
          </div>

          {/* Navigation arrows */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              goToPrevious();
            }}
            className="absolute left-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white p-1.5 rounded-full transition-colors"
            aria-label="Previous object"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <button
            onClick={(e) => {
              e.stopPropagation();
              goToNext();
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white p-1.5 rounded-full transition-colors"
            aria-label="Next object"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>

          {/* Object counter */}
          <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/70 text-white px-2 py-0.5 rounded text-xs">
            {currentObjectIndex + 1} / {detectedObjects.length}
          </div>

          {/* Object Info Badge - Top Right */}
          <div className="absolute top-2 right-2 bg-black/70 text-white px-2 py-1 rounded text-xs">
            <p className="font-semibold">{currentObject.label}</p>
            <p className="text-[10px]">{(currentObject.confidence * 100).toFixed(0)}% confidence</p>
          </div>
        </div>

        {/* Bottom - Google Lens hint */}
        <div className="flex-shrink-0 px-1 pb-1">
          <p className="text-[11px] text-gray-500 leading-snug">
            Right-click the image and select <span className="font-medium text-gray-700">Search image with Google Lens</span> to search for similar images on Google.
          </p>
        </div>
      </div>
    </div>
  );
}

function FramesWidget({ frames }: { frames: string[] }) {
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0);
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });
  const widgetRef = React.useRef<HTMLDivElement>(null);
  if (frames.length === 0) {
    return (
      <div className="p-3 flex items-center justify-center h-full text-gray-400 text-sm">
        No frame data
      </div>
    );
  }

  const goToPrevious = () => {
    setCurrentFrameIndex((prev) => (prev > 0 ? prev - 1 : frames.length - 1));
  };

  const goToNext = () => {
    setCurrentFrameIndex((prev) => (prev < frames.length - 1 ? prev + 1 : 0));
  };

  const handleButtonHover = (buttonName: string, event: React.MouseEvent<HTMLButtonElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setTooltipPosition({ x: rect.right - 30, y: rect.top + (rect.height / 2) });
    setHoveredButton(buttonName);
  };

  const handleButtonLeave = () => {
    setHoveredButton(null);
  };

  // Mock AI descriptions for each frame
  const aiDescriptions = [
    "Firefighter visible through dense black smoke inside a burning building. Flames visible along the left wall, ceiling partially obscured by fog.",
    "Close-up of active fire consuming wooden roof beams. Embers falling. Heavy smoke reduces visibility to near zero.",
    "Wide interior shot showing two firefighters advancing with a hose. Flames engulf the rear wall and spread toward the ceiling.",
    "Thick smoke fills the upper half of the frame. A firefighter crouches low, silhouetted against orange flames in the background.",
    "Partial roof collapse visible in upper right corner. Debris on the floor. A hose stream cuts through the smoke toward the fire.",
    "Extreme heat distortion visible. Firefighter in full gear braces against a door frame as flames surge from an adjacent room.",
    "Overhead view of fire spreading across the floor. Charred structural elements visible. Water stream impacts the base of the flames.",
    "Evacuation in progress — two figures move toward an exit through thick smoke. Flames reflected on a broken window pane."
  ];

  // Truncate text to max characters
  const truncateText = (text: string, maxLength: number = 120) => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength).trim() + '...';
  };

  return (
    <div ref={widgetRef} className="relative h-full w-full overflow-visible">
      <div className="h-full w-full flex flex-col p-2 gap-2">
        {/* Top - Frame display with navigation */}
        <div className="relative flex items-center justify-center bg-black rounded-lg overflow-hidden flex-1">
          <img
            src={frames[currentFrameIndex]}
            alt={`Frame ${currentFrameIndex + 1}`}
            className="max-w-full max-h-full object-contain"
          />

          {/* Navigation arrows */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              goToPrevious();
            }}
            className="absolute left-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white p-1.5 rounded-full transition-colors"
            aria-label="Previous frame"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <button
            onClick={(e) => {
              e.stopPropagation();
              goToNext();
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white p-1.5 rounded-full transition-colors"
            aria-label="Next frame"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>

          {/* Frame counter */}
          <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/70 text-white px-2 py-0.5 rounded text-xs">
            {currentFrameIndex + 1} / {frames.length}
          </div>
        </div>

        {/* Bottom - AI Overview (left) and Action Buttons (right) */}
        <div className="flex gap-2 flex-shrink-0">
          {/* Left - AI Overview Section */}
          <div className="flex-1">
            <div className="flex items-center gap-1 mb-1">
              <svg className="w-4 h-4 text-[#0065f4]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              <h3 className="text-xs font-semibold text-gray-700">AI Overview</h3>
            </div>
            <p className="text-xs text-gray-600 leading-snug">
              {(() => {
                const text = aiDescriptions[currentFrameIndex] || "AI analysis of the current frame.";
                const firstSentence = text.split(/\.\s+/)[0] + '.';
                return firstSentence;
              })()}
            </p>
          </div>

          {/* Right - Action Buttons */}
          <div className="flex flex-col gap-2">
            {/* Stitching Button */}
            <button
              onClick={(e) => e.stopPropagation()}
              onMouseEnter={(e) => handleButtonHover('stitching', e)}
              onMouseLeave={handleButtonLeave}
              className="bg-[#0065f4] hover:bg-[#0052cc] text-white px-4 py-2 rounded-lg text-xs font-medium transition-colors whitespace-nowrap shadow-sm"
            >
              Stitching
            </button>
          </div>
        </div>

        {/* Google Lens hint */}
        <div className="flex-shrink-0 pt-1">
          <p className="text-[11px] text-gray-500 leading-snug">
            Right-click the image and select <span className="font-medium text-gray-700">Search image with Google Lens</span> to search for similar images on Google.
          </p>
        </div>
      </div>

      {/* Fixed position tooltip */}
      {hoveredButton && (
        <div
          className="fixed px-3 py-2 bg-gray-900/60 text-white text-sm rounded-lg shadow-lg z-[9999] pointer-events-none -translate-y-1/2"
          style={{ left: `${tooltipPosition.x}px`, top: `${tooltipPosition.y}px` }}
        >
          {hoveredButton === 'stitching' && 'Combine frames into one panoramic image'}
        </div>
      )}
    </div>
  );
}

function MapWidget() {
  const [showStreetView, setShowStreetView] = useState(false);
  const [tooltipVisible, setTooltipVisible] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });

  const handleButtonHover = (e: React.MouseEvent<HTMLButtonElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setTooltipPosition({ x: rect.right - 30, y: rect.top + rect.height / 2 });
    setTooltipVisible(true);
  };

  return (
    <div className="h-full w-full flex flex-col">
      <div className="flex-1 relative bg-gray-100">
        <iframe
          src="https://maps.google.com/maps?q=55.6058,13.0007&t=m&z=16&output=embed&iwloc=near"
          className="w-full h-full border-0"
          title="Map of Malmö, Sweden"
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
        />
        <div className="absolute top-2 left-2 bg-white px-2 py-1 rounded shadow text-xs">
          55.6058° N, 13.0007° E — Malmö, Sweden
        </div>
      </div>
      <div className="flex-shrink-0 p-2">
        <button
          onClick={(e) => { e.stopPropagation(); setShowStreetView(true); }}
          onMouseEnter={handleButtonHover}
          onMouseLeave={() => setTooltipVisible(false)}
          className="bg-[#0065f4] hover:bg-[#0052cc] text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap shadow-sm w-full"
        >
          Google Street View
        </button>
        {tooltipVisible && createPortal(
          <div
            className="fixed px-3 py-2 bg-gray-900/60 text-white text-sm rounded-lg shadow-lg z-[9999] pointer-events-none -translate-y-1/2"
            style={{ left: `${tooltipPosition.x}px`, top: `${tooltipPosition.y}px` }}
          >
            Find the location on Google Street View
          </div>,
          document.body
        )}
      </div>

      {showStreetView && createPortal(
        <div className="fixed inset-0 bg-black/60 z-[10000] flex items-center justify-center" onClick={() => setShowStreetView(false)}>
          <div className="bg-white rounded-xl shadow-2xl w-[800px] max-w-[95vw] h-[520px] flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
              <h3 className="text-base font-semibold text-gray-900">Google Street View — 55.6058° N, 13.0007° E, Malmö</h3>
              <button onClick={() => setShowStreetView(false)} className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors text-gray-500 hover:text-gray-800">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1">
              <iframe
                src="https://www.google.com/maps/embed?pb=!4v1715000000000!6m8!1m7!1sCAoSLEFGMVFpcE1PX3VOaXRSVzl6eUtMc1FtUjBWRVN6TmlDZGhzVGd3bWFoYlR3!2m2!1d55.6058!2d13.0007!3f90!4f10!5f0.7820865974627469"
                className="w-full h-full border-0"
                title="Google Street View Malmö City Center"
                allowFullScreen
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
              />
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}

function MetadataWidget() {
  const [viewMode, setViewMode] = useState<'metadata' | 'analyze'>('analyze');

  const metadata = {
    messageType: "metadata",
    videoId: "5cd0c0b1-da37",
    format: {
      filename: "sample_video.mp4",
      nb_streams: 2,
      nb_programs: 0,
      format_name: "mov,mp4,m4a,3gp,3g2,mj2",
      format_long_name: "QuickTime / MOV",
      start_time: "0.000000",
      duration: "45.133000",
      size: "8947293",
      bit_rate: "1586743",
      probe_score: 100,
      tags: {
        major_brand: "isom",
        minor_version: "512",
        compatible_brands: "isomiso2avc1mp41",
        encoder: "Lavf58.76.100",
        creation_time: "2024-03-15T14:23:45.000000Z",
        com_android_version: "11",
        com_android_manufacturer: "Samsung",
        com_android_model: "SM-G991B",
        location: "+55.6058+013.0007/",
        location_eng: "Malmö, Skåne, Sweden",
        com_apple_quicktime_location_iso6709: "+55.6058+013.0007+18.000/"
      }
    },
    streams: [
      {
        index: 0,
        codec_name: "h264",
        codec_long_name: "H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10",
        profile: "High",
        codec_type: "video",
        codec_tag_string: "avc1",
        codec_tag: "0x31637661",
        width: 1920,
        height: 1080,
        coded_width: 1920,
        coded_height: 1080,
        closed_captions: 0,
        film_grain: 0,
        has_b_frames: 2,
        sample_aspect_ratio: "1:1",
        display_aspect_ratio: "16:9",
        pix_fmt: "yuv420p",
        level: 42,
        color_range: "tv",
        color_space: "bt709",
        color_transfer: "bt709",
        color_primaries: "bt709",
        chroma_location: "left",
        refs: 1,
        is_avc: "true",
        nal_length_size: "4",
        r_frame_rate: "30/1",
        avg_frame_rate: "30/1",
        time_base: "1/15360",
        start_pts: 0,
        start_time: "0.000000",
        duration_ts: 693043,
        duration: "45.133000",
        bit_rate: "1452389",
        bits_per_raw_sample: "8",
        nb_frames: "1354",
        extradata_size: 47,
        tags: {
          creation_time: "2024-03-15T14:23:45.000000Z",
          language: "und",
          handler_name: "VideoHandler",
          vendor_id: "[0][0][0][0]",
          encoder: "AVC Coding"
        },
        side_data_list: [
          {
            side_data_type: "Display Matrix",
            rotation: 0
          }
        ],
        disposition: {
          default: 1,
          dub: 0,
          original: 0,
          comment: 0,
          lyrics: 0,
          karaoke: 0,
          forced: 0,
          hearing_impaired: 0,
          visual_impaired: 0,
          clean_effects: 0,
          attached_pic: 0,
          timed_thumbnails: 0
        }
      },
      {
        index: 1,
        codec_name: "aac",
        codec_long_name: "AAC (Advanced Audio Coding)",
        profile: "LC",
        codec_type: "audio",
        codec_tag_string: "mp4a",
        codec_tag: "0x6134706d",
        sample_fmt: "fltp",
        sample_rate: "48000",
        channels: 2,
        channel_layout: "stereo",
        bits_per_sample: 0,
        r_frame_rate: "0/0",
        avg_frame_rate: "0/0",
        time_base: "1/48000",
        start_pts: 0,
        start_time: "0.000000",
        duration_ts: 2166336,
        duration: "45.132000",
        bit_rate: "128000",
        max_bit_rate: "128000",
        nb_frames: "2115",
        extradata_size: 5,
        tags: {
          creation_time: "2024-03-15T14:23:45.000000Z",
          language: "eng",
          handler_name: "SoundHandler",
          vendor_id: "[0][0][0][0]"
        },
        disposition: {
          default: 1,
          dub: 0,
          original: 0,
          comment: 0,
          lyrics: 0,
          karaoke: 0,
          forced: 0,
          hearing_impaired: 0,
          visual_impaired: 0,
          clean_effects: 0,
          attached_pic: 0,
          timed_thumbnails: 0
        }
      }
    ]
  };

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="flex justify-start gap-2 p-3 pb-2 flex-shrink-0">
        <button
          onClick={(e) => {
            e.stopPropagation();
            setViewMode('analyze');
          }}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            viewMode === 'analyze'
              ? 'bg-[#0065f4] text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          Analysis
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            setViewMode('metadata');
          }}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            viewMode === 'metadata'
              ? 'bg-[#0065f4] text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          Original
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {viewMode === 'metadata' ? (
          <pre className="text-xs font-mono whitespace-pre-wrap break-words">
            {JSON.stringify(metadata, null, 2)}
          </pre>
        ) : (
          <div className="space-y-4 text-sm">
            <div className="border-b-2 border-gray-300 pb-2">
              <h3 className="font-bold text-gray-800 text-base">METADATA ANALYSIS – OBJECTIVE OVERVIEW</h3>
            </div>

            {/* Verification Assessment */}
            <div className="bg-blue-50 border border-blue-200 rounded p-3">
              <h4 className="font-semibold text-blue-900 mb-2">VERIFICATION ASSESSMENT</h4>
              <p className="text-blue-800 text-xs leading-relaxed">
                This video was recorded on a {metadata.format.tags.com_android_manufacturer} {metadata.format.tags.com_android_model}
                running Android {metadata.format.tags.com_android_version} on {new Date(metadata.format.tags.creation_time).toLocaleDateString('en-US', {
                  year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit'
                })}. The file uses standard H.264/AAC encoding typical of mobile devices.
                Metadata indicates proper encoding with {metadata.streams[0].nb_frames} video frames at 30fps over {Math.floor(parseFloat(metadata.format.duration))} seconds.
                No rotation applied. Video resolution is Full HD 1080p (1920x1080).
              </p>
            </div>

            {/* Missing Data Alert */}
            <div className="bg-yellow-50 border border-yellow-200 rounded p-3">
              <h4 className="font-semibold text-yellow-900 mb-2">⚠ NOTICE</h4>
              <p className="text-yellow-800 text-xs leading-relaxed">
                The recording date (March 15, 2024) indicates that this is not a recent recording.<br /><br />
                Age of the file should be considered when evaluating relevance or authenticity context.
              </p>
            </div>

            {/* Creation Time / Timestamps */}
            <div>
              <h4 className="font-semibold text-gray-800 mb-2">CREATION TIME / TIMESTAMPS</h4>
              <p className="text-gray-700 leading-relaxed text-xs">
                <strong>Creation Time:</strong> {metadata.format.tags.creation_time || 'Not available'}<br />
                <strong>Date:</strong> {new Date(metadata.format.tags.creation_time).toLocaleDateString('en-US', {
                  year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'
                })}<br />
                <strong>Start Time:</strong> {metadata.format.start_time}s<br />
                <strong>Duration:</strong> {metadata.format.duration}s ({Math.floor(parseFloat(metadata.format.duration) / 60)}m {Math.floor(parseFloat(metadata.format.duration) % 60)}s)<br />
                <strong>Video Start:</strong> {metadata.streams[0].tags.creation_time || 'Not available'}
              </p>
            </div>

            {/* Device Information */}
            <div>
              <h4 className="font-semibold text-gray-800 mb-2">DEVICE INFORMATION</h4>
              <p className="text-gray-700 leading-relaxed text-xs">
                <strong>Manufacturer:</strong> {metadata.format.tags.com_android_manufacturer || 'Not available'}<br />
                <strong>Model:</strong> {metadata.format.tags.com_android_model || 'Not available'}<br />
                <strong>OS Version:</strong> Android {metadata.format.tags.com_android_version || 'Unknown'}<br />
                <strong>Encoder:</strong> {metadata.format.tags.encoder || 'Not available'}<br />
                <strong>Video Encoder:</strong> {metadata.streams[0].tags.encoder || 'Not available'}
              </p>
            </div>

            {/* Location Information */}
            <div>
              <h4 className="font-semibold text-gray-800 mb-2">LOCATION</h4>
              <p className="text-gray-700 leading-relaxed text-xs">
                <strong>Location:</strong> {metadata.format.tags.location_eng}<br />
                <strong>Coordinates:</strong> 55.6058° N, 13.0007° E<br />
                <strong>ISO 6709:</strong> {metadata.format.tags.com_apple_quicktime_location_iso6709}
              </p>
            </div>

            {/* Video Technical Specifications */}
            <div>
              <h4 className="font-semibold text-gray-800 mb-2">VIDEO TECHNICAL SPECIFICATIONS</h4>
              <p className="text-gray-700 leading-relaxed text-xs">
                <strong>Codec:</strong> {metadata.streams[0].codec_long_name}<br />
                <strong>Resolution:</strong> {metadata.streams[0].width} x {metadata.streams[0].height} pixels (Full HD 1080p)<br />
                <strong>Aspect Ratio:</strong> {metadata.streams[0].display_aspect_ratio}<br />
                <strong>Profile:</strong> {metadata.streams[0].profile}<br />
                <strong>Level:</strong> {metadata.streams[0].level}<br />
                <strong>Pixel Format:</strong> {metadata.streams[0].pix_fmt}<br />
                <strong>Color Space:</strong> {metadata.streams[0].color_space}<br />
                <strong>Color Range:</strong> {metadata.streams[0].color_range}<br />
                <strong>Color Transfer:</strong> {metadata.streams[0].color_transfer}<br />
                <strong>Bit Rate:</strong> {Math.round(parseInt(metadata.streams[0].bit_rate) / 1000)} kbps
              </p>
            </div>

            {/* Frame Structure */}
            <div>
              <h4 className="font-semibold text-gray-800 mb-2">FRAME STRUCTURE</h4>
              <p className="text-gray-700 leading-relaxed text-xs">
                <strong>Frame Rate:</strong> {metadata.streams[0].r_frame_rate} fps (30 fps)<br />
                <strong>Average Frame Rate:</strong> {metadata.streams[0].avg_frame_rate} fps<br />
                <strong>Total Frames:</strong> {metadata.streams[0].nb_frames}<br />
                <strong>Has B-Frames:</strong> {metadata.streams[0].has_b_frames > 0 ? `Yes (${metadata.streams[0].has_b_frames})` : 'No'}<br />
                <strong>Reference Frames:</strong> {metadata.streams[0].refs}<br />
                <strong>Time Base:</strong> {metadata.streams[0].time_base}<br />
                <strong>AVC:</strong> {metadata.streams[0].is_avc}<br />
                <strong>NAL Length Size:</strong> {metadata.streams[0].nal_length_size}
              </p>
            </div>

            {/* Audio Metadata */}
            <div>
              <h4 className="font-semibold text-gray-800 mb-2">AUDIO METADATA</h4>
              <p className="text-gray-700 leading-relaxed text-xs">
                <strong>Codec:</strong> {metadata.streams[1].codec_long_name}<br />
                <strong>Profile:</strong> {metadata.streams[1].profile}<br />
                <strong>Sample Rate:</strong> {metadata.streams[1].sample_rate} Hz<br />
                <strong>Channels:</strong> {metadata.streams[1].channels} ({metadata.streams[1].channel_layout})<br />
                <strong>Bit Rate:</strong> {Math.round(parseInt(metadata.streams[1].bit_rate) / 1000)} kbps<br />
                <strong>Max Bit Rate:</strong> {Math.round(parseInt(metadata.streams[1].max_bit_rate) / 1000)} kbps<br />
                <strong>Sample Format:</strong> {metadata.streams[1].sample_fmt}<br />
                <strong>Language:</strong> {metadata.streams[1].tags.language}<br />
                <strong>Duration:</strong> {metadata.streams[1].duration}s<br />
                <strong>Total Audio Frames:</strong> {metadata.streams[1].nb_frames}
              </p>
            </div>

            {/* Side Data / Extra Tracks */}
            <div>
              <h4 className="font-semibold text-gray-800 mb-2">SIDE DATA / EXTRA TRACKS</h4>
              <p className="text-gray-700 leading-relaxed text-xs">
                <strong>Side Data Type:</strong> {metadata.streams[0].side_data_list?.[0]?.side_data_type || 'None'}<br />
                <strong>Rotation:</strong> {metadata.streams[0].side_data_list?.[0]?.rotation !== undefined ? `${metadata.streams[0].side_data_list[0].rotation}°` : 'Not specified'}<br />
                <strong>Extra Data Size (Video):</strong> {metadata.streams[0].extradata_size} bytes<br />
                <strong>Extra Data Size (Audio):</strong> {metadata.streams[1].extradata_size} bytes<br />
                <strong>Subtitle Tracks:</strong> None<br />
                <strong>Attachment Tracks:</strong> None
              </p>
            </div>

            {/* File Format Details */}
            <div>
              <h4 className="font-semibold text-gray-800 mb-2">FILE FORMAT DETAILS</h4>
              <p className="text-gray-700 leading-relaxed text-xs">
                <strong>Format:</strong> {metadata.format.format_long_name}<br />
                <strong>Major Brand:</strong> {metadata.format.tags.major_brand}<br />
                <strong>Compatible Brands:</strong> {metadata.format.tags.compatible_brands}<br />
                <strong>File Size:</strong> {(parseInt(metadata.format.size) / 1024 / 1024).toFixed(2)} MB<br />
                <strong>Overall Bit Rate:</strong> {Math.round(parseInt(metadata.format.bit_rate) / 1000)} kbps<br />
                <strong>Number of Streams:</strong> {metadata.format.nb_streams}<br />
                <strong>Probe Score:</strong> {metadata.format.probe_score}/100
              </p>
            </div>

            {/* GPS Metadata */}
            <div>
              <h4 className="font-semibold text-gray-800 mb-2">GPS METADATA</h4>
              <p className="text-gray-700 leading-relaxed text-xs">
                <strong>Location:</strong> Malmö, Skåne, Sweden<br />
                <strong>Coordinates:</strong> 55.6058° N, 13.0007° E<br />
                <strong>Altitude:</strong> 18 m<br />
                <strong>GPS Time:</strong> 2024-03-15T14:23:45Z
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Dashboard() {
  console.log('Dashboard rendering...');
  const allFilters: FilterType[] = ['source', 'frames', 'transcription', 'detection', 'metadata', 'map', 'notes'];
  const [activeFilters, setActiveFilters] = useState<FilterType[]>(['source', 'frames', 'transcription', 'detection', 'metadata', 'map', 'notes']);
  const [projectName, setProjectName] = useState(() => {
    // Load saved project name from localStorage
    return localStorage.getItem('projectName') || '';
  });
  const [customizeMode, setCustomizeMode] = useState(false);
  const [notes, setNotes] = useState('');
  const [videoUrl, setVideoUrl] = useState('');
  const [videoFrames, setVideoFrames] = useState<string[]>([]);
  const [showSaved, setShowSaved] = useState(() => {
    // Show saved state if there's already a project name
    return !!localStorage.getItem('projectName');
  });
  const [expandedWidget, setExpandedWidget] = useState<FilterType | null>(null);
  const [showHelpCenter, setShowHelpCenter] = useState(false);
  const [showWidgetHelp, setShowWidgetHelp] = useState<FilterType | null>(null);
  const [helpPopupPosition, setHelpPopupPosition] = useState({ top: 0, left: 0, width: 0 });
  const [transcriptionLanguage, setTranscriptionLanguage] = useState<'both' | 'norwegian' | 'english'>('both');
  const [expandedFrameIndex, setExpandedFrameIndex] = useState(0);
  const [showExportPopup, setShowExportPopup] = useState(false);
  const [exportFilters, setExportFilters] = useState<FilterType[]>(allFilters);

  // Ensure all filters are active on mount
  useEffect(() => {
    if (activeFilters.length !== allFilters.length) {
      setActiveFilters(allFilters);
    }
  }, []);

  // Auto-save project name with debounce
  useEffect(() => {
    if (projectName === localStorage.getItem('projectName')) return;

    const timeoutId = setTimeout(() => {
      if (projectName) {
        localStorage.setItem('projectName', projectName);
        setShowSaved(true);
      } else {
        localStorage.removeItem('projectName');
        setShowSaved(false);
      }
    }, 800);

    return () => clearTimeout(timeoutId);
  }, [projectName]);



  // Default layout based on the reference image
  const defaultWidgetOrder: WidgetConfig[] = [
    { id: 'source', rowSpan: 1 },       // Row 1, column 1
    { id: 'frames', rowSpan: 1 },       // Row 1, column 2
    { id: 'detection', rowSpan: 1 },    // Row 1, column 3
    { id: 'transcription', rowSpan: 2 }, // Row 2-3, column 1 (tall)
    { id: 'metadata', rowSpan: 2 },     // Row 2-3, column 2 (tall)
    { id: 'map', rowSpan: 1 },          // Row 2, column 3
    { id: 'notes', rowSpan: 1 },        // Row 3, column 3
  ];

  const [widgetOrder, setWidgetOrder] = useState<WidgetConfig[]>([
    { id: 'source', rowSpan: 1 },
    { id: 'frames', rowSpan: 1 },
    { id: 'detection', rowSpan: 1 },
    { id: 'transcription', rowSpan: 2 },
    { id: 'metadata', rowSpan: 2 },
    { id: 'map', rowSpan: 1 },
    { id: 'notes', rowSpan: 1 },
  ]);

  const resetToDefault = () => {
    setWidgetOrder([...defaultWidgetOrder]);
  };



  const toggleFilter = (filter: FilterType) => {
    setActiveFilters(prev =>
      prev.includes(filter)
        ? prev.filter(f => f !== filter)
        : [...prev, filter]
    );
  };

  const selectAll = () => {
    if (activeFilters.length === allFilters.length) {
      setActiveFilters([]);
    } else {
      setActiveFilters(allFilters);
    }
  };

  const moveWidget = (dragIndex: number, hoverIndex: number) => {
    const newOrder = [...widgetOrder];
    const draggedItem = newOrder[dragIndex];
    newOrder.splice(dragIndex, 1);
    newOrder.splice(hoverIndex, 0, draggedItem);
    setWidgetOrder(newOrder);
  };

  const isActive = (filter: FilterType) => activeFilters.includes(filter);

  const getWidgetTitle = (id: FilterType): string => {
    switch (id) {
      case 'source': return 'Media/Source';
      case 'frames': return 'Frames (1 frame per second)';
      case 'metadata': return 'Metadata';
      case 'notes': return 'Notes';
      case 'map': return 'Map';
      case 'transcription': return 'Transcription & Translation';
      case 'detection': return 'Object Detection';
    }
  };

  const getWidgetHelpText = (id: FilterType): string => {
    switch (id) {
      case 'source':
        return 'Source is where you upload the video you want to verify. You can either upload a video from your computer or import one by pasting a file URL. Once the video is added, it will appear as a preview in the Source section. This video is then used as the original material for the verification process.';
      case 'frames':
        return 'Frames shows the keyframes extracted from your video at a rate of 1 frame per second. This Widget lets you investigate each frame one by one. Use Stitching to combine multiple frames into a wider image, which can reveal more visual context and help with geolocation or scene matching. Use Image Reverse Search to check whether a frame has appeared online before, which can help identify reused, misleading, or miscaptioned content.';
      case 'transcription':
        return 'Transcription & Translation automatically extracts spoken content from the video and shows it with timestamps. The transcript appears in the original spoken language and is translated into English. Use this tab to check what is being said, compare speech with the video context, and identify claims that may need further verification.';
      case 'detection':
        return 'Object Detection helps identify specific objects that appear in the video frames. Use this widget to focus on details such as signs, vehicles, buildings, products, or other visual clues that may support verification. Use Image Reverse Search on detected objects to check whether they appear elsewhere online. This can help confirm locations, identify reused visuals, or find inconsistencies in how the video is presented.';
      case 'metadata':
        return 'Metadata is hidden technical information stored inside a video file. It can include details such as when the video was created, what device or software was used, file format, duration, and sometimes location data. Start by checking the timestamps, device information, and any editing or software traces. These details can help you spot missing, changed, or inconsistent information that may support or challenge the video\'s authenticity. To get a better understanding of the metadata, click "Analyze", and you will be presented with an easy-to-understand version.';
      case 'map':
        return 'Map shows location information connected to the video when GPS or geolocation data is available. The marker indicates where the video may have been recorded based on the metadata. Use this widget to compare the claimed location with the map, nearby roads, landmarks, terrain, or other visual clues from the video. This can help confirm whether the video matches the location it is presented as showing.';
      case 'notes':
        return 'Notes lets you write down observations, questions, links, and findings while verifying a video. This is useful for keeping track of what you have checked, what still needs to be verified, and why you reached a certain conclusion. If you give a case a name and save it, your notes make it easier to return to the investigation later. They are also helpful when collaborating, like this others can more quickly understand your verification process and continue the work from where you left off.';
    }
  };

  // Calculate active widgets
  const widgetCount = activeFilters.length;

  // Determine grid columns based on number of active widgets
  const getGridCols = () => {
    if (widgetCount === 0) return 'grid-cols-1';
    if (widgetCount === 1) return 'grid-cols-1';
    if (widgetCount === 2) return 'grid-cols-2';
    if (widgetCount <= 4) return 'grid-cols-2';
    return 'grid-cols-3';
  };

  console.log('About to return...');

  return (
    <div className="min-h-screen p-8">
      <h1 className="text-2xl">Dashboard Loading...</h1>
      <p>If you see this, Dashboard is returning JSX correctly</p>
    </div>
  );
}

// Original return - temporarily commented
/*
  return (
    <div className="min-h-screen relative" style={{ backgroundColor: '#f7f7f7', backgroundImage: 'linear-gradient(to bottom, #ffffff 0%, #ffffff 60px, rgba(255,255,255,0.85) 120px, rgba(255,255,255,0.5) 220px, rgba(255,255,255,0.1) 380px, transparent 500px), radial-gradient(circle, #d0d0d0 1px, transparent 1px)', backgroundSize: '100% 100%, 20px 20px' }}>
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
        <img src={logoImage} alt="Logo" className="h-[60px] w-auto" />

        <div className="flex items-center gap-4">
          <button
            onClick={() => {
              if (confirm('Start a new case? Any unsaved changes will be lost.')) {
                setProjectName('');
                setVideoUrl('');
                setVideoFrames([]);
                setNotes('');
                setShowSaved(false);
                localStorage.removeItem('projectName');
              }
            }}
            className="group flex items-center gap-1.5 bg-white px-3 py-1.5 rounded-[20px] shadow-md border border-gray-200 hover:shadow-lg transition-all"
          >
            <svg className="w-[16px] h-[16px]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path className="stroke-black group-hover:stroke-[#0065f4]" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            <span className="text-[13px] text-black group-hover:text-[#0065f4]">New Case</span>
          </button>

          <button
            onClick={() => setCustomizeMode(!customizeMode)}
            className={`group flex items-center gap-1.5 bg-white px-3 py-1.5 rounded-[20px] shadow-md border border-gray-200 hover:shadow-lg transition-all ${customizeMode ? 'border-[#0065f4]' : ''}`}
          >
            <svg className="w-[20px] h-[20px]" fill="none" viewBox="0 0 29 30">
              <path d={svgPaths.p11351100} className={customizeMode ? "stroke-[#0065f4]" : "stroke-black group-hover:stroke-[#0065f4]"} strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
            </svg>
            <span className={`text-[13px] ${customizeMode ? 'text-[#0065f4]' : 'text-black group-hover:text-[#0065f4]'}`}>Customize Dashboard</span>
          </button>

          <button
            onClick={() => setShowExportPopup(true)}
            className="group flex items-center gap-1.5 bg-white px-3 py-1.5 rounded-[20px] shadow-md border border-gray-200 hover:shadow-lg transition-all"
          >
            <svg className="w-[16px] h-[16px]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path className="stroke-black group-hover:stroke-[#0065f4]" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="text-[13px] text-black group-hover:text-[#0065f4]">Export to PDF</span>
          </button>

          <button
            onClick={() => setShowHelpCenter(true)}
            className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors group"
            aria-label="Help"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 32 32">
              <path d={svgPaths.p2a930080} className="fill-black group-hover:fill-[#0065f4] transition-colors" />
            </svg>
          </button>
        </div>
      </header>

      {/* Filter Buttons */}
      <div className="pt-8 pb-6 max-w-[1400px] mx-auto px-20">
        <div className="flex justify-center">
          <div className="inline-flex gap-3 w-full max-w-[1200px] overflow-visible">
            {/* Select All */}
            <button
              onClick={selectAll}
              className={`relative flex-1 px-4 py-3 text-sm font-medium rounded-lg transition-all whitespace-nowrap cursor-pointer shadow-sm overflow-visible ${
                activeFilters.length === allFilters.length
                  ? 'bg-[#deecff] border border-[#0065f4] text-[#0065f4] hover:bg-[#b3d9ff]'
                  : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-200 hover:text-[#0065f4]'
              }`}
            >
              Select All
              {activeFilters.length !== allFilters.length && (
                <span className="absolute -top-1.5 -right-1.5 w-5 h-5 flex items-center justify-center rounded-full bg-[#0065f4] text-white select-none" style={{boxShadow: '0 0 0 1px rgba(255,255,255,0.9)'}}>
                  <Plus size={10} strokeWidth={2} />
                </span>
              )}
            </button>

            {([
              { id: 'source', label: 'Source' },
              { id: 'frames', label: 'Frames' },
              { id: 'transcription', label: 'Transcription & Translation' },
              { id: 'detection', label: 'Object Detection' },
              { id: 'metadata', label: 'Metadata' },
              { id: 'map', label: 'Map' },
              { id: 'notes', label: 'Notes' },
            ] as { id: FilterType; label: string }[]).map(({ id, label }) => (
              <button
                key={id}
                onClick={() => toggleFilter(id)}
                className={`relative flex-1 px-4 py-3 text-sm font-medium rounded-lg transition-all whitespace-nowrap cursor-pointer shadow-sm overflow-visible ${
                  isActive(id)
                    ? 'bg-[#deecff] border border-[#0065f4] text-[#0065f4] hover:bg-[#b3d9ff]'
                    : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-200 hover:text-[#0065f4]'
                }`}
              >
                {label}
                <span
                  className={`absolute -top-1.5 -right-1.5 w-5 h-5 flex items-center justify-center rounded-full select-none transition-colors ${
                    isActive(id)
                      ? 'bg-white text-[#0065f4]'
                      : 'bg-[#0065f4] text-white'
                  }`}
                  style={{boxShadow: isActive(id) ? '0 0 0 1px #0065f4' : '0 0 0 1px rgba(255,255,255,0.9)'}}
                >
                  {isActive(id) ? <Minus size={10} strokeWidth={2} /> : <Plus size={10} strokeWidth={2} />}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <main className="px-20 pt-6 w-full max-w-full mx-auto pb-24 overflow-x-hidden">
        {customizeMode && (
          <div className="mb-3 p-3 bg-[#deecff] border border-[#0065f4] rounded-lg text-[#0065f4] text-sm flex items-center justify-between max-w-[1400px] mx-auto">
            <span className="font-medium">Drag and drop widgets to rearrange them</span>
            <div className="flex items-center gap-2">
              <button
                onClick={resetToDefault}
                className="px-3 py-1.5 bg-white text-[#0065f4] border border-[#0065f4] rounded-lg text-xs font-medium hover:bg-[#deecff] transition-colors flex items-center gap-1.5"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Reset to Default
              </button>
              <button
                onClick={() => setCustomizeMode(false)}
                className="w-6 h-6 flex items-center justify-center rounded-md text-[#0065f4] hover:bg-[#0065f4] hover:text-white transition-colors"
                aria-label="Close customize dashboard"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        )}

        <div className="max-w-[1400px] mx-auto">
          {/* Main Grid - All widgets */}
          <div className={`grid ${getGridCols()} gap-8 auto-rows-min`}>
            {/* Render widgets based on widgetOrder state */}
            {widgetOrder
              .filter(widget => isActive(widget.id))
              .map((widget, index) => {
                const filter = widget.id;

                if (filter === 'source') {
                  return (
                    <div key="source" className="min-h-[300px]">
                      <DraggableWidget
                        id="source"
                        index={index}
                        rowSpan={1}
                        title={getWidgetTitle('source')}
                        customizeMode={customizeMode}
                        moveWidget={moveWidget}
                        onExpand={() => setExpandedWidget('source')}
                        onHelp={(rect) => {
                          setHelpPopupPosition({ top: rect.top + window.scrollY, left: rect.left + window.scrollX, width: rect.width });
                          setShowWidgetHelp('source');
                        }}
                      >
                        <SourceWidget videoUrl={videoUrl} setVideoUrl={setVideoUrl} onFramesExtracted={setVideoFrames} />
                      </DraggableWidget>
                    </div>
                  );
                }

                if (filter === 'frames') {
                  return (
                    <div key="frames" className="min-h-[300px]">
                      <DraggableWidget
                        id="frames"
                        index={index}
                        rowSpan={1}
                        title={getWidgetTitle('frames')}
                        customizeMode={customizeMode}
                        moveWidget={moveWidget}
                        onExpand={() => setExpandedWidget('frames')}
                        onHelp={(rect) => {
                          setHelpPopupPosition({ top: rect.top + window.scrollY, left: rect.left + window.scrollX, width: rect.width });
                          setShowWidgetHelp('frames');
                        }}
                      >
                        <FramesWidget frames={videoFrames} />
                      </DraggableWidget>
                    </div>
                  );
                }

                if (filter === 'transcription') {
                  return (
                    <div key="transcription" className="row-span-2 h-[668px]">
                      <DraggableWidget
                        id="transcription"
                        index={index}
                        rowSpan={2}
                        title={getWidgetTitle('transcription')}
                        customizeMode={customizeMode}
                        moveWidget={moveWidget}
                        onExpand={() => setExpandedWidget('transcription')}
                        onHelp={(rect) => {
                          setHelpPopupPosition({ top: rect.top + window.scrollY, left: rect.left + window.scrollX, width: rect.width });
                          setShowWidgetHelp('transcription');
                        }}
                        onSound={() => {
                          // Play audio functionality - for now just log
                          console.log('Play transcription audio');
                        }}
                      >
                        {videoUrl ? (
                          <div className="p-3 h-full overflow-auto">
                            <div className="mb-3">
                              <div className="flex gap-1.5 mb-2">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setTranscriptionLanguage('both');
                                  }}
                                  className={`px-2 py-1 rounded-md text-[11px] font-medium transition-colors ${
                                    transcriptionLanguage === 'both'
                                      ? 'bg-[#0065f4] text-white'
                                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                                  }`}
                                >
                                  Both
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setTranscriptionLanguage('norwegian');
                                  }}
                                  className={`px-2 py-1 rounded-md text-[11px] font-medium transition-colors ${
                                    transcriptionLanguage === 'norwegian'
                                      ? 'bg-[#0065f4] text-white'
                                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                                  }`}
                                >
                                  Original
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setTranscriptionLanguage('english');
                                  }}
                                  className={`px-2 py-1 rounded-md text-[11px] font-medium transition-colors ${
                                    transcriptionLanguage === 'english'
                                      ? 'bg-[#0065f4] text-white'
                                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                                  }`}
                                >
                                  EN
                                </button>
                              </div>
                              <p className="text-[11px] text-gray-600">
                                Detected language: <span className="font-medium text-black">Swedish</span>
                              </p>
                            </div>
                            <div className="space-y-4">
                              {[
                                { time: '00:00:00 - 00:00:02', original: 'Elden sprider sig snabbt', translation: 'The fire is spreading fast' },
                                { time: '00:00:02 - 00:00:04', original: 'Vi måste backa lite', translation: 'We need to pull back' },
                                { time: '00:00:04 - 00:00:06', original: 'Mer vatten på kanten', translation: 'More water on the edge' },
                                { time: '00:00:06 - 00:00:11', original: 'Håll dig lågt, sikten är nästan noll', translation: 'Stay low, visibility is almost zero' },
                                { time: '00:00:11 - 00:00:12', original: 'Mer vatten hit', translation: 'More water here' },
                                { time: '00:00:12 - 00:00:13', original: 'Trycket är för svagt', translation: 'The pressure is too low' },
                                { time: '00:00:13 - 00:00:15', original: 'Taket knakar, det kan rasa när som helst', translation: 'The ceiling is cracking, it could collapse any second' },
                                { time: '00:00:15 - 00:00:17', original: 'Vi måste evakuera den här sidan nu', translation: 'We need to evacuate this side now' },
                              ].map(({ time, original, translation }) => (
                                <div key={time}>
                                  <div className="flex items-center gap-2 mb-1">
                                    <p className="text-[#0065f4] text-[13px]">{time}</p>
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24">
                                      <path d="M11 5L6 9H2V15H6L11 19V5Z" fill="#757575" stroke="#757575" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                      <path d="M15.54 8.46C16.4774 9.39764 17.0039 10.6692 17.0039 11.995C17.0039 13.3208 16.4774 14.5924 15.54 15.53" stroke="#757575" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                    </svg>
                                  </div>
                                  {transcriptionLanguage !== 'english' && (
                                    <p className="text-black text-[13px] leading-normal mb-0.5">{original}</p>
                                  )}
                                  {transcriptionLanguage !== 'norwegian' && (
                                    <p className="text-gray-600 text-[13px] leading-normal italic mb-3">{translation}</p>
                                  )}
                                  {transcriptionLanguage === 'norwegian' && <div className="mb-3"></div>}
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <div className="p-3 flex items-center justify-center h-full text-gray-400 text-sm">
                            No transcription data
                          </div>
                        )}
                      </DraggableWidget>
                    </div>
                  );
                }

                if (filter === 'detection') {
                  return (
                    <div key="detection" className="min-h-[300px]">
                      <DraggableWidget
                        id="detection"
                        index={index}
                        rowSpan={1}
                        title={getWidgetTitle('detection')}
                        customizeMode={customizeMode}
                        moveWidget={moveWidget}
                        onExpand={() => setExpandedWidget('detection')}
                        onHelp={(rect) => {
                          setHelpPopupPosition({ top: rect.top + window.scrollY, left: rect.left + window.scrollX, width: rect.width });
                          setShowWidgetHelp('detection');
                        }}
                      >
                        <ObjectDetectionWidget frames={videoFrames} />
                      </DraggableWidget>
                    </div>
                  );
                }

                if (filter === 'metadata') {
                  return (
                    <div key="metadata" className="row-span-2 h-[668px]">
                      <DraggableWidget
                        id="metadata"
                        index={index}
                        rowSpan={2}
                        title={getWidgetTitle('metadata')}
                        customizeMode={customizeMode}
                        moveWidget={moveWidget}
                        onExpand={() => setExpandedWidget('metadata')}
                        onHelp={(rect) => {
                          setHelpPopupPosition({ top: rect.top + window.scrollY, left: rect.left + window.scrollX, width: rect.width });
                          setShowWidgetHelp('metadata');
                        }}
                      >
                        {videoUrl ? (
                          <MetadataWidget />
                        ) : (
                          <div className="p-3 flex items-center justify-center h-full text-gray-400 text-sm">
                            No metadata available
                          </div>
                        )}
                      </DraggableWidget>
                    </div>
                  );
                }

                if (filter === 'map') {
                  return (
                    <div key="map" className="min-h-[300px]">
                      <DraggableWidget
                        id="map"
                        index={index}
                        rowSpan={1}
                        title={getWidgetTitle('map')}
                        customizeMode={customizeMode}
                        moveWidget={moveWidget}
                        onExpand={() => setExpandedWidget('map')}
                        onHelp={(rect) => {
                          setHelpPopupPosition({ top: rect.top + window.scrollY, left: rect.left + window.scrollX, width: rect.width });
                          setShowWidgetHelp('map');
                        }}
                      >
                        {videoUrl ? (
                          <MapWidget />
                        ) : (
                          <div className="p-3 flex items-center justify-center h-full text-gray-400 text-sm">
                            No location data available
                          </div>
                        )}
                      </DraggableWidget>
                    </div>
                  );
                }

                if (filter === 'notes') {
                  return (
                    <div key="notes" className="min-h-[300px]">
                      <DraggableWidget
                        id="notes"
                        index={index}
                        rowSpan={1}
                        title={getWidgetTitle('notes')}
                        isYellow={true}
                        customizeMode={customizeMode}
                        moveWidget={moveWidget}
                        onExpand={() => setExpandedWidget('notes')}
                        onHelp={(rect) => {
                          setHelpPopupPosition({ top: rect.top + window.scrollY, left: rect.left + window.scrollX, width: rect.width });
                          setShowWidgetHelp('notes');
                        }}
                      >
                        <textarea
                          value={notes}
                          onChange={(e) => {
                            const newValue = e.target.value;
                            const cursorPos = e.target.selectionStart;

                            // Check if user just typed a dash at the beginning of a line or after newline
                            if (newValue.length > notes.length && newValue.charAt(cursorPos - 1) === '-') {
                              const beforeCursor = newValue.substring(0, cursorPos - 1);
                              const afterCursor = newValue.substring(cursorPos);

                              // Check if dash is at start of line (beginning or after newline)
                              if (beforeCursor === '' || beforeCursor.endsWith('\n')) {
                                const updatedValue = beforeCursor + '• ' + afterCursor;
                                setNotes(updatedValue);
                                setTimeout(() => {
                                  e.target.selectionStart = e.target.selectionEnd = cursorPos + 1;
                                }, 0);
                                return;
                              }
                            }

                            setNotes(newValue);
                          }}
                          onClick={(e) => e.stopPropagation()}
                          placeholder="Write your notes here..."
                          className="w-full h-full p-3 bg-transparent border-none outline-none resize-none text-black placeholder-gray-400"
                          style={{ fontSize: '14px', lineHeight: '1.5' }}
                        />
                      </DraggableWidget>
                    </div>
                  );
                }

                return null;
              })}
          </div>
        </div>
      </main>

      {/* Expanded Widget Overlay */}
      {expandedWidget && (
        <div className="fixed inset-0 bg-white z-50 flex flex-col">
          {/* Header with close button */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <h2 className="text-2xl font-semibold text-gray-800">{getWidgetTitle(expandedWidget)}</h2>
            <button
              onClick={() => setExpandedWidget(null)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              aria-label="Close"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Expanded widget content */}
          <div className="flex-1 overflow-auto p-6">
            {expandedWidget === 'source' && (
              <div className="h-full">
                <SourceWidget videoUrl={videoUrl} setVideoUrl={setVideoUrl} onFramesExtracted={setVideoFrames} />
              </div>
            )}
            {expandedWidget === 'frames' && (
              videoFrames.length === 0 ? (
                <div className="p-6 flex items-center justify-center h-full text-gray-400">
                  No frame data
                </div>
              ) : (
                <div className="h-full flex gap-6 p-6">
                  {/* Left side - Frame display with navigation */}
                  <div className="relative flex items-center justify-center bg-black rounded-lg overflow-hidden flex-1">
                    <img
                      src={videoFrames[expandedFrameIndex]}
                      alt={`Frame ${expandedFrameIndex + 1}`}
                      className="max-w-full max-h-full object-contain"
                    />

                    {/* Navigation arrows */}
                    <button
                      onClick={() => setExpandedFrameIndex((prev) => (prev > 0 ? prev - 1 : videoFrames.length - 1))}
                      className="absolute left-4 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white p-2 rounded-full transition-colors"
                      aria-label="Previous frame"
                    >
                      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                      </svg>
                    </button>

                    <button
                      onClick={() => setExpandedFrameIndex((prev) => (prev < videoFrames.length - 1 ? prev + 1 : 0))}
                      className="absolute right-4 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white p-2 rounded-full transition-colors"
                      aria-label="Next frame"
                    >
                      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </button>

                    {/* Frame counter */}
                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black/70 text-white px-3 py-1 rounded text-sm">
                      {expandedFrameIndex + 1} / {videoFrames.length}
                    </div>
                  </div>

                  {/* Right side - AI Overview and Action Buttons */}
                  <div className="w-[300px] flex flex-col gap-4">
                    {/* AI Overview Section */}
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <svg className="w-5 h-5 text-[#0065f4]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        <h3 className="text-sm font-semibold text-gray-700">AI Overview</h3>
                      </div>
                      <p className="text-sm text-gray-600 leading-relaxed">
                        {[
                          "Firefighter visible through dense black smoke inside a burning building.",
                          "Close-up of active fire consuming wooden roof beams.",
                          "Wide interior shot showing two firefighters advancing with a hose.",
                          "Thick smoke fills the upper half of the frame.",
                          "Partial roof collapse visible in upper right corner.",
                          "Extreme heat distortion visible.",
                          "Overhead view of fire spreading across the floor.",
                          "Evacuation in progress — two figures move toward an exit through thick smoke."
                        ][expandedFrameIndex] || "AI analysis of the current frame."}
                      </p>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex flex-col gap-3">
                      {/* Stitching Button */}
                      <button
                        className="bg-[#0065f4] hover:bg-[#0052cc] text-white px-6 py-3 rounded-lg text-sm font-medium transition-colors whitespace-nowrap shadow-sm w-full"
                      >
                        Stitching
                      </button>
                    </div>

                    {/* Google Lens hint */}
                    <p className="text-xs text-gray-500 leading-snug">
                      Right-click the image and select <span className="font-medium text-gray-700">Search image with Google Lens</span> to search for similar images on Google.
                    </p>
                  </div>
                </div>
              )
            )}
            {expandedWidget === 'transcription' && (
              videoUrl ? (
                <div className="p-6 h-full overflow-auto">
                  <div className="mb-4">
                    <div className="flex gap-2 mb-3">
                      <button
                        onClick={() => setTranscriptionLanguage('both')}
                        className={`px-4 py-2 rounded-lg text-[15px] font-medium transition-colors ${
                          transcriptionLanguage === 'both'
                            ? 'bg-[#0065f4] text-white'
                            : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        }`}
                      >
                        Both
                      </button>
                      <button
                        onClick={() => setTranscriptionLanguage('norwegian')}
                        className={`px-4 py-2 rounded-lg text-[15px] font-medium transition-colors ${
                          transcriptionLanguage === 'norwegian'
                            ? 'bg-[#0065f4] text-white'
                            : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        }`}
                      >
                        Original
                      </button>
                      <button
                        onClick={() => setTranscriptionLanguage('english')}
                        className={`px-4 py-2 rounded-lg text-[15px] font-medium transition-colors ${
                          transcriptionLanguage === 'english'
                            ? 'bg-[#0065f4] text-white'
                            : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        }`}
                      >
                        EN
                      </button>
                    </div>
                    <p className="text-[15px] text-gray-600">
                      Detected language: <span className="font-medium text-black">Swedish</span>
                    </p>
                  </div>
                  <div className="space-y-6">
                    {[
                      { time: '00:00:00 - 00:00:02', original: 'Elden sprider sig snabbt', translation: 'The fire is spreading fast' },
                      { time: '00:00:02 - 00:00:04', original: 'Vi måste backa lite', translation: 'We need to pull back' },
                      { time: '00:00:04 - 00:00:06', original: 'Mer vatten på kanten', translation: 'More water on the edge' },
                      { time: '00:00:06 - 00:00:11', original: 'Håll dig lågt, sikten är nästan noll', translation: 'Stay low, visibility is almost zero' },
                      { time: '00:00:11 - 00:00:12', original: 'Mer vatten hit', translation: 'More water here' },
                      { time: '00:00:12 - 00:00:13', original: 'Trycket är för svagt', translation: 'The pressure is too low' },
                      { time: '00:00:13 - 00:00:15', original: 'Taket knakar, det kan rasa när som helst', translation: 'The ceiling is cracking, it could collapse any second' },
                      { time: '00:00:15 - 00:00:17', original: 'Vi måste evakuera den här sidan nu', translation: 'We need to evacuate this side now' },
                    ].map(({ time, original, translation }) => (
                      <div key={time}>
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-[#0065f4] text-[15px]">{time}</p>
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24">
                            <path d="M11 5L6 9H2V15H6L11 19V5Z" fill="#757575" stroke="#757575" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            <path d="M15.54 8.46C16.4774 9.39764 17.0039 10.6692 17.0039 11.995C17.0039 13.3208 16.4774 14.5924 15.54 15.53" stroke="#757575" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        </div>
                        {transcriptionLanguage !== 'english' && (
                          <p className="text-black text-[15px] leading-normal mb-1">{original}</p>
                        )}
                        {transcriptionLanguage !== 'norwegian' && (
                          <p className="text-gray-600 text-[15px] leading-normal italic mb-4">{translation}</p>
                        )}
                        {transcriptionLanguage === 'norwegian' && <div className="mb-4"></div>}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="p-6 flex items-center justify-center h-full text-gray-400">
                  No transcription data
                </div>
              )
            )}
            {expandedWidget === 'detection' && (
              <div className="h-full">
                <ObjectDetectionWidget frames={videoFrames} />
              </div>
            )}
            {expandedWidget === 'metadata' && (
              videoUrl ? (
                <MetadataExpandedView />
              ) : (
                <div className="p-6 flex items-center justify-center h-full text-gray-400">
                  No metadata available
                </div>
              )
            )}
            {expandedWidget === 'map' && (
              videoUrl ? (
                <MapWidget />
              ) : (
                <div className="p-6 flex items-center justify-center h-full text-gray-400">
                  No location data available
                </div>
              )
            )}
            {expandedWidget === 'notes' && (
              <div className="h-full bg-[#eff6ff] rounded-xl p-6">
                <textarea
                  value={notes}
                  onChange={(e) => {
                    const newValue = e.target.value;
                    const cursorPos = e.target.selectionStart;

                    // Check if user just typed a dash at the beginning of a line or after newline
                    if (newValue.length > notes.length && newValue.charAt(cursorPos - 1) === '-') {
                      const beforeCursor = newValue.substring(0, cursorPos - 1);
                      const afterCursor = newValue.substring(cursorPos);

                      // Check if dash is at start of line (beginning or after newline)
                      if (beforeCursor === '' || beforeCursor.endsWith('\n')) {
                        const updatedValue = beforeCursor + '• ' + afterCursor;
                        setNotes(updatedValue);
                        setTimeout(() => {
                          e.target.selectionStart = e.target.selectionEnd = cursorPos + 1;
                        }, 0);
                        return;
                      }
                    }

                    setNotes(newValue);
                  }}
                  onClick={(e) => e.stopPropagation()}
                  placeholder="Write your notes here..."
                  className="w-full h-full bg-transparent border-none outline-none resize-none text-black placeholder-gray-400"
                  style={{ fontSize: '14px', lineHeight: '1.5' }}
                />
              </div>
            )}
          </div>
        </div>
      )}



      {/* Export Popup */}
      {showExportPopup && (
        <div className="fixed inset-0 bg-black/60 z-[10000] flex items-center justify-center" onClick={() => setShowExportPopup(false)}>
          <div className="bg-white rounded-xl shadow-2xl w-[450px] max-w-[95vw] flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Export Findings to PDF</h3>
              <button onClick={() => setShowExportPopup(false)} className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors text-gray-500 hover:text-gray-800">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6">
              <p className="text-sm text-gray-600 mb-4">
                Select which sections to include in your PDF report:
              </p>

              {/* Select All */}
              <div className="mb-3 pb-3 border-b border-gray-200">
                <label className="flex items-center gap-3 cursor-pointer hover:bg-gray-50 p-2 rounded-lg transition-colors">
                  <input
                    type="checkbox"
                    checked={exportFilters.length === allFilters.length}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setExportFilters(allFilters);
                      } else {
                        setExportFilters([]);
                      }
                    }}
                    className="w-4 h-4 text-[#0065f4] border-gray-300 rounded focus:ring-[#0065f4]"
                  />
                  <span className="text-sm font-semibold text-gray-900">Select All</span>
                </label>
              </div>

              {/* Individual Filters */}
              <div className="space-y-2 mb-6 max-h-[300px] overflow-y-auto">
                {[
                  { id: 'source', label: 'Source' },
                  { id: 'frames', label: 'Frames' },
                  { id: 'transcription', label: 'Transcription & Translation' },
                  { id: 'detection', label: 'Object Detection' },
                  { id: 'metadata', label: 'Metadata' },
                  { id: 'map', label: 'Map' },
                  { id: 'notes', label: 'Notes' },
                ].map(({ id, label }) => (
                  <label key={id} className="flex items-center gap-3 cursor-pointer hover:bg-gray-50 p-2 rounded-lg transition-colors">
                    <input
                      type="checkbox"
                      checked={exportFilters.includes(id as FilterType)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setExportFilters([...exportFilters, id as FilterType]);
                        } else {
                          setExportFilters(exportFilters.filter(f => f !== id));
                        }
                      }}
                      className="w-4 h-4 text-[#0065f4] border-gray-300 rounded focus:ring-[#0065f4]"
                    />
                    <span className="text-sm text-gray-700">{label}</span>
                  </label>
                ))}
              </div>

              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowExportPopup(false)}
                  className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    alert(`Exporting PDF with: ${exportFilters.join(', ')}`);
                    setShowExportPopup(false);
                  }}
                  disabled={exportFilters.length === 0}
                  className="px-4 py-2 text-white bg-[#0065f4] rounded-lg hover:bg-[#0052cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Export PDF
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Widget Help Popup */}
      {showWidgetHelp && (
        <div
          className="absolute z-50 pointer-events-auto"
          style={{
            top: `${helpPopupPosition.top}px`,
            left: `${helpPopupPosition.left}px`,
            width: `${helpPopupPosition.width}px`,
          }}
        >
          <div className="bg-white rounded-xl shadow-2xl overflow-hidden">
            {/* Close button */}
            <button
              onClick={() => setShowWidgetHelp(null)}
              className="absolute top-4 right-4 p-2 hover:bg-gray-100 rounded-lg transition-colors z-10"
              aria-label="Close"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            {/* Help Content */}
            <div className="p-4">
              <h2 className="text-base font-bold text-gray-800 mb-2 pr-8">{getWidgetTitle(showWidgetHelp)}</h2>
              <p className="text-xs text-gray-700 leading-relaxed">{getWidgetHelpText(showWidgetHelp)}</p>
            </div>
          </div>
        </div>
      )}

      {/* Help Center Fullscreen */}
      {showHelpCenter && (
        <div className="fixed inset-0 bg-white z-50 flex flex-col">
          {/* Header with close button */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <h2 className="text-2xl font-semibold text-gray-800">Help Center</h2>
            <button
              onClick={() => setShowHelpCenter(false)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              aria-label="Close"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Help Center Content */}
          <div className="flex-1 overflow-auto">
            <HelpCenter />
          </div>
        </div>
      )}
    </div>
  );
}
*/

// Simplified Dashboard above for testing
// Will restore full version once we confirm it works

export default function App() {
  return (
    <DndProvider backend={HTML5Backend}>
      <Dashboard />
    </DndProvider>
  );
}

