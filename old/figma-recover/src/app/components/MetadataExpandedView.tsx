import { useState } from 'react';

export function MetadataExpandedView() {
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
        com_android_model: "SM-G991B"
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
      <div className="flex-1 grid grid-cols-2 gap-4 overflow-hidden p-6">
        {/* Left column - Analyzed */}
        <div className="flex flex-col overflow-hidden border border-gray-200 rounded-lg shadow-sm">
          <div className="px-4 py-3 bg-gray-100 border-b border-gray-200 flex-shrink-0">
            <h3 className="font-semibold text-gray-800">Analysis</h3>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <div className="space-y-4 text-sm">

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
          </div>
        </div>

        {/* Right column - Raw Metadata */}
        <div className="flex flex-col overflow-hidden border border-gray-200 rounded-lg shadow-sm">
          <div className="px-4 py-3 bg-gray-100 border-b border-gray-200 flex-shrink-0">
            <h3 className="font-semibold text-gray-800">Original Metadata</h3>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <pre className="text-xs font-mono whitespace-pre-wrap break-words">
              {JSON.stringify(metadata, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
