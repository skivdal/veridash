import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, useRef, useState } from "react";

import { ApiError } from "../../api/fetcher";
import {
  completeSourceMediaUploadApiUploadsMediaIdCompletePost,
  getGetProjectSourceMediaApiProjectsProjectIdMediaGetQueryKey,
  getListProjectAnalysesApiProjectsProjectIdAnalysesGetQueryKey,
  reserveSourceMediaApiProjectsProjectIdMediaPost,
  useGetProjectSourceMediaApiProjectsProjectIdMediaGet,
} from "../../api/generated/client";
import type { SourceMediaResponse } from "../../api/generated/schemas";
import { type UploadProgress, uploadSourceMedia } from "./uploadSourceMedia";

type UploadStage = "reserving" | "uploading" | "validating";

interface SourceMediaPanelProps {
  projectId: string;
  projectState: string;
}

export function SourceMediaPanel({
  projectId,
  projectState,
}: SourceMediaPanelProps) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const [uploadStage, setUploadStage] = useState<UploadStage>("reserving");
  const [uploadProgress, setUploadProgress] = useState<UploadProgress>();
  const mediaQuery = useGetProjectSourceMediaApiProjectsProjectIdMediaGet(
    projectId,
    { query: { retry: false } },
  );
  const media =
    mediaQuery.data?.status === 200 ? mediaQuery.data.data : undefined;
  const noSourceMedia =
    mediaQuery.error instanceof ApiError && mediaQuery.error.status === 404;

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const abortController = new AbortController();
      abortControllerRef.current = abortController;
      setUploadProgress(undefined);
      setUploadStage("reserving");
      const reservation = await reserveSourceMediaApiProjectsProjectIdMediaPost(
        projectId,
        {
          original_filename: file.name,
        },
      );
      if (reservation.status !== 200) {
        throw new Error("The source video could not be reserved.");
      }

      setUploadStage("uploading");
      await uploadSourceMedia(
        reservation.data.id,
        file,
        setUploadProgress,
        abortController.signal,
      );

      setUploadStage("validating");
      const completion =
        await completeSourceMediaUploadApiUploadsMediaIdCompletePost(
          reservation.data.id,
        );
      if (completion.status !== 200) {
        throw new Error("The source video could not be finalized.");
      }
      return completion.data;
    },
    onSuccess: (sourceMedia) => {
      queryClient.setQueryData(
        getGetProjectSourceMediaApiProjectsProjectIdMediaGetQueryKey(projectId),
        { data: sourceMedia, status: 200, headers: new Headers() },
      );
      void queryClient.invalidateQueries({
        queryKey:
          getListProjectAnalysesApiProjectsProjectIdAnalysesGetQueryKey(
            projectId,
          ),
      });
    },
    onSettled: () => {
      abortControllerRef.current = null;
      if (inputRef.current !== null) inputRef.current.value = "";
    },
  });

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.item(0);
    if (file === null || file === undefined) return;
    uploadMutation.reset();
    uploadMutation.mutate(file);
  }

  const shownMedia = uploadMutation.data ?? media;
  const isArchived = projectState === "archived";
  const errorMessage = getUploadError(uploadMutation.error);

  return (
    <article className="analysis-card source-media-card" id="source-media">
      <div className="analysis-card-heading">
        <div>
          <p className="card-eyebrow">Project source</p>
          <h2>Source video</h2>
        </div>
        <SourceStatus
          isLoading={mediaQuery.isPending}
          isUploading={uploadMutation.isPending}
          media={shownMedia}
        />
      </div>

      {shownMedia?.upload_state === "uploaded" ? (
        <UploadedSource media={shownMedia} />
      ) : (
        <div className="source-upload-body">
          <p>
            Add the single source video for this project. Once it passes
            validation, it becomes immutable and analysis can be scheduled from
            its verified content hash.
          </p>

          {shownMedia?.upload_state === "failed" ? (
            <p className="form-error" role="alert">
              {shownMedia.failure_message ??
                "The selected file was not recognized as a video."}
            </p>
          ) : null}
          {mediaQuery.isError && !noSourceMedia ? (
            <p className="form-error" role="alert">
              {mediaQuery.error instanceof Error
                ? mediaQuery.error.message
                : "The source-video state could not be loaded."}
            </p>
          ) : null}
          {errorMessage === undefined ? null : (
            <p className="form-error" role="alert">
              {errorMessage}
            </p>
          )}

          {uploadMutation.isPending ? (
            <UploadProgressView
              progress={uploadProgress}
              stage={uploadStage}
              onCancel={() => abortControllerRef.current?.abort()}
            />
          ) : (
            <div className="source-picker">
              {isArchived ? (
                <button
                  className="button button-primary"
                  type="button"
                  disabled
                >
                  Choose video
                </button>
              ) : (
                <label
                  className="button button-primary"
                  htmlFor="source-video-file"
                >
                  {shownMedia === undefined
                    ? "Choose video"
                    : "Choose video again"}
                </label>
              )}
              <input
                ref={inputRef}
                className="visually-hidden"
                id="source-video-file"
                type="file"
                accept="video/*,.mkv,.m2ts,.mts,.ts"
                disabled={isArchived}
                onChange={selectFile}
              />
              <span>
                {isArchived
                  ? "Restore this project before uploading."
                  : "The browser will show transfer progress before server validation."}
              </span>
            </div>
          )}
        </div>
      )}
    </article>
  );
}

function SourceStatus({
  isLoading,
  isUploading,
  media,
}: {
  isLoading: boolean;
  isUploading: boolean;
  media: SourceMediaResponse | undefined;
}) {
  let label = "Waiting for video";
  let className = "status-pill";
  if (isLoading) label = "Checking…";
  if (media?.upload_state === "failed") {
    label = "Needs attention";
    className += " status-pill-error";
  }
  if (media?.upload_state === "uploaded") {
    label = "Ready";
    className += " status-pill-ready";
  }
  if (isUploading) label = "Uploading";
  return <span className={className}>{label}</span>;
}

function UploadProgressView({
  progress,
  stage,
  onCancel,
}: {
  progress: UploadProgress | undefined;
  stage: UploadStage;
  onCancel: () => void;
}) {
  const percent =
    progress?.totalBytes === undefined || progress.totalBytes === 0
      ? undefined
      : Math.min(100, (progress.loadedBytes / progress.totalBytes) * 100);
  const label =
    stage === "reserving"
      ? "Preparing upload…"
      : stage === "validating"
        ? "Validating video…"
        : percent === undefined
          ? "Uploading video…"
          : `Uploading video… ${Math.round(percent)}%`;

  return (
    <div className="upload-progress" aria-live="polite">
      <div className="upload-progress-label">
        <span>{label}</span>
        {stage === "uploading" ? (
          <button className="link-button" type="button" onClick={onCancel}>
            Cancel
          </button>
        ) : null}
      </div>
      <progress
        aria-label="Source-video upload progress"
        max={100}
        value={stage === "uploading" ? percent : undefined}
      />
      {stage === "validating" ? (
        <small>
          The server is verifying that the file contains a video stream.
        </small>
      ) : null}
    </div>
  );
}

function UploadedSource({ media }: { media: SourceMediaResponse }) {
  return (
    <div className="uploaded-source">
      <video
        className="source-video"
        controls
        preload="metadata"
        src={`/api/media/${encodeURIComponent(media.id)}/content`}
      >
        <track kind="captions" />
      </video>
      <div className="source-file-details">
        <strong>{media.original_filename}</strong>
        <span>
          {formatBytes(media.size_bytes)}
          {media.media_type === null ? "" : ` · ${media.media_type}`}
        </span>
        {media.sha256_hex === null ? null : (
          <code title={media.sha256_hex}>{shortHash(media.sha256_hex)}</code>
        )}
      </div>
    </div>
  );
}

function formatBytes(sizeBytes: number | null): string {
  if (sizeBytes === null) return "Unknown size";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let value = sizeBytes;
  let unit = units[0];
  for (const candidate of units) {
    unit = candidate;
    if (value < 1024 || candidate === units.at(-1)) break;
    value /= 1024;
  }
  return `${value < 10 && unit !== "B" ? value.toFixed(1) : Math.round(value)} ${unit}`;
}

function shortHash(hash: string): string {
  return `sha256:${hash.slice(0, 12)}…${hash.slice(-8)}`;
}

function getUploadError(error: unknown): string | undefined {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return error === null ? undefined : "The source video could not be uploaded.";
}
