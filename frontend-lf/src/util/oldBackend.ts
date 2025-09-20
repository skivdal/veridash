import { useEffect } from 'react';
import { Project } from "../schema";
import type { co } from "jazz-tools";
import type {
  BackendError as OldBackendError,
  BackendProgress as OldBackendProgress,
  KeyFramesResponse as OldKeyFramesResponse,
  MapResponse as OldMapResponse,
  MetadataResponse as OldMetadataResponse,
  ObjDetectResponse as OldObjDetectResponse,
  SourceResponse as OldSourceResponse,
  StitchingResponse as OldStitchingResponse,
  TranscriptionResponse as OldTranscriptionResponse,
} from './oldBackendMessage';
import { BackendData, BackendMessage, KeyFramesResponse, MapResponse, MetadataResponse, ObjDetectResponse, SourceResponse, StitchingResponse, TranscriptionResponse } from '../backendSchema';
import { getFileByInfo, type FileInfo } from './fileTransfer';

type OldBackendMessage =
  OldBackendProgress |
  OldBackendError |
  OldSourceResponse |
  OldMetadataResponse |
  OldTranscriptionResponse |
  OldMapResponse |
  OldKeyFramesResponse |
  OldObjDetectResponse |
  OldStitchingResponse;

function handleMessage(data: OldBackendMessage, project: co.loaded<typeof Project>) {
  if ("progress" in data) {
    return;
  } else if ("error" in data) {
    return;
  }

  if (data.messageType === "source") {
    const msg = data as OldSourceResponse;

    project.jobState?.$jazz.push(BackendMessage.create({
      videoId: msg.videoId,
      filename: msg.filename,
      imageId: msg.imageId,
      sourceKeyFrames: msg.sourceKeyFrames,
      timestamp: new Date(),
      progressOrData: BackendData.create({
        messageType: "data",
        data: SourceResponse.create({
          moduleType: "source",
          uploadUrl: msg.uploadUrl,
          downloadUrl: msg.downloadUrl,
        }),
      }),
    }));
  }
  else if (data.messageType === "metadata") {
    const msg = data as OldMetadataResponse;

    project.jobState?.$jazz.push(BackendMessage.create({
      videoId: msg.videoId,
      filename: msg.filename,
      imageId: msg.imageId,
      sourceKeyFrames: msg.sourceKeyFrames,
      timestamp: new Date(),
      progressOrData: BackendData.create({
        messageType: "data",
        data: MetadataResponse.create({
          moduleType: "metadata",
          streams: msg.streams,
          format: msg.format,
        }),
      }),
    }));
  }
  else if (data.messageType === "transcription") {
    const msg = data as OldTranscriptionResponse;

    project.jobState?.$jazz.push(BackendMessage.create({
      videoId: msg.videoId,
      filename: msg.filename,
      imageId: msg.imageId,
      sourceKeyFrames: msg.sourceKeyFrames,
      timestamp: new Date(),
      progressOrData: BackendData.create({
        messageType: "data",
        data: TranscriptionResponse.create({
          moduleType: "transcription",
          transcription: {
            text: msg.transcription.text,
            language: msg.transcription.language,
            segments: msg.transcription.segments.map(x => JSON.stringify(x)),
          },
        }),
      }),
    }));
  }
  else if (data.messageType === "map") {
    const msg = data as OldMapResponse;

    project.jobState?.$jazz.push(BackendMessage.create({
      videoId: msg.videoId,
      filename: msg.filename,
      imageId: msg.imageId,
      sourceKeyFrames: msg.sourceKeyFrames,
      timestamp: new Date(),
      progressOrData: BackendData.create({
        messageType: "data",
        data: MapResponse.create({
          moduleType: "map",
          latlng: msg.latlng && msg.latlng.length >= 2 ? [msg.latlng[0], msg.latlng[1]] : undefined,
        }),
      }),
    }));
  }
  else if (data.messageType === "keyframes") {
    const msg = data as OldKeyFramesResponse;

    project.jobState?.$jazz.push(BackendMessage.create({
      videoId: msg.videoId,
      filename: msg.filename,
      imageId: msg.imageId,
      sourceKeyFrames: msg.sourceKeyFrames,
      timestamp: new Date(),
      progressOrData: BackendData.create({
        messageType: "data",
        data: KeyFramesResponse.create({
          moduleType: "keyframes",
          urls: msg.urls,
        }),
      }),
    }));
  }
  else if (data.messageType === "objectdetection") {
    const msg = data as OldObjDetectResponse;

    project.jobState?.$jazz.push(BackendMessage.create({
      videoId: msg.videoId,
      filename: msg.filename,
      imageId: msg.imageId,
      sourceKeyFrames: msg.sourceKeyFrames,
      timestamp: new Date(),
      progressOrData: BackendData.create({
        messageType: "data",
        data: ObjDetectResponse.create({
          moduleType: "objectdetection",
          urls: msg.urls,
          keyFrameNumbers: msg.keyFrameNumbers,
        }),
      }),
    }));
  }
  else if (data.messageType === "stitching") {
    const msg = data as OldStitchingResponse;

    project.jobState?.$jazz.push(BackendMessage.create({
      videoId: msg.videoId,
      filename: msg.filename,
      imageId: msg.imageId,
      sourceKeyFrames: msg.sourceKeyFrames,
      timestamp: new Date(),
      progressOrData: BackendData.create({
        messageType: "data",
        data: StitchingResponse.create({
          moduleType: "stitching",
          url: msg.url,
          sourceKeyFrames: msg.sourceKeyFrames,
        }),
      }),
    }));
  }
  else {
    console.error("Unrecognized message type", data.messageType, "for message", data);
  }
}

export function useOldBackend(url: string, projectId: string | undefined, doListen: boolean) {
  useEffect(() => {
    if (!projectId || !doListen)
      return;

    const socket = new WebSocket(url);
    (async () => {
      const project = await Project.load(projectId);
      if (!project?.files ||
        project.files.length === 0 ||
        !project.files[0]?.hash ||
        project.jobState?.length !== 0)
        return;  // if no file availiable or jobs already run

      // Ensure the socket is open
      await new Promise<void>((resolve, reject) => {
        if (socket.readyState === socket.OPEN) {
          resolve();
        } else {
          socket.onopen = () => {
            resolve();
          };
          socket.onerror = (error) => {
            reject(error);
          };
        }
      });

      socket.addEventListener("message", (event) => {
        if (!project) {
          console.warn("Could not find Project with id", projectId);
          return;
        }

        try {
          const data = JSON.parse(event.data);
          handleMessage(data, project);

          // Upload file and ask for more
          (async () => {
            if (!data?.uploadUrl || !project.files || project.files.length === 0)
              return;

            const f = await getFileByInfo(project.files[0] as FileInfo);
            const res = await fetch(data.uploadUrl, {
              method: "PUT",
              body: f,
              headers: {
                "Content-Type": f.type,
              },
            });

            if (res.ok) {
              const reqs = ["map", "keyframes", "metadata", "transcription", "osmtags", "objectdetection"];
              for (const r of reqs) {
                socket.send(
                  JSON.stringify({
                    messageType: r,
                    videoId: data.videoId,
                  })
                )
              }
            }
            else {
              console.error("Upload failed :(")
            }
          })();
        } catch (e) {
          console.warn("Invalid JSON from websocket:", event.data);
        }
      });

      socket.addEventListener("error", (event) => {
        console.error("WebSocket error:", event);
      });

      socket.addEventListener("close", () => {
        console.log("WebSocket disconnected");
      });

      socket.send(
        JSON.stringify({
          messageType: "source",
          filename: `${project.files[0].name}:${project.files[0].hash}`,
        })
      );
    })();

    return () => {
      socket.close();
    };
  }, [url, projectId, doListen]);
}

