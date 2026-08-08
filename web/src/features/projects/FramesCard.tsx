import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError } from "../../api/fetcher";
import {
  getListProjectAnalysesApiProjectsProjectIdAnalysesGetQueryKey,
  useCreateFrameStitchApiProjectsProjectIdAnalysesFrameStitchesPost,
  useListProjectAnalysisArtifactsApiProjectsProjectIdAnalysesJobIdArtifactsGet,
} from "../../api/generated/client";
import type {
  AnalysisArtifactResponse,
  AnalysisJobResponse,
} from "../../api/generated/schemas";
import { AnalysisProvenance } from "./AnalysisProvenance";

interface FramesCardProps {
  projectId: string;
  job: AnalysisJobResponse | undefined;
  cancelPendingJobId: string | undefined;
  onCancel: (jobId: string) => void;
  retryPendingJobId: string | undefined;
  onRetry: (jobId: string) => void;
  stitchJobs: AnalysisJobResponse[];
  readOnly: boolean;
}

interface FrameIndexItem {
  outputName: string;
  ordinal: number;
  timestampSeconds: number;
}

export function FramesCard({
  projectId,
  job,
  cancelPendingJobId,
  onCancel,
  retryPendingJobId,
  onRetry,
  stitchJobs,
  readOnly,
}: FramesCardProps) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [selectedOutputNames, setSelectedOutputNames] = useState<string[]>([]);
  const createStitch =
    useCreateFrameStitchApiProjectsProjectIdAnalysesFrameStitchesPost({
      mutation: {
        onSuccess: async (response) => {
          if (response.status !== 201) return;
          setSelectedOutputNames([]);
          await queryClient.invalidateQueries({
            queryKey:
              getListProjectAnalysesApiProjectsProjectIdAnalysesGetQueryKey(
                projectId,
              ),
          });
        },
      },
    });
  const artifacts =
    useListProjectAnalysisArtifactsApiProjectsProjectIdAnalysesJobIdArtifactsGet(
      projectId,
      job?.id ?? "",
      { query: { enabled: job?.state === "succeeded", retry: false } },
    );
  const artifactList =
    artifacts.data?.status === 200 ? artifacts.data.data : [];
  const indexArtifact = artifactList.find(
    (artifact) => artifact.output_name === "index",
  );
  const frames = parseFrameIndex(indexArtifact?.json_payload)
    .map((item) => ({
      item,
      artifact: artifactList.find(
        (candidate) => candidate.output_name === item.outputName,
      ),
    }))
    .filter(
      (
        frame,
      ): frame is {
        item: FrameIndexItem;
        artifact: AnalysisArtifactResponse;
      } => frame.artifact !== undefined,
    );
  const latestStitch = stitchJobs.at(-1);
  const stitchError =
    createStitch.error instanceof ApiError
      ? createStitch.error.message
      : undefined;

  function toggleSelection(outputName: string) {
    createStitch.reset();
    setSelectedOutputNames((current) =>
      current.includes(outputName)
        ? current.filter((name) => name !== outputName)
        : current.length < 12
          ? [...current, outputName]
          : current,
    );
  }

  if (job?.state !== "succeeded" || indexArtifact === undefined) {
    const latestAttempt = job?.attempts.at(-1);
    const canCancel =
      job !== undefined &&
      ["waiting_for_dependencies", "ready", "running", "retry_wait"].includes(
        job.state,
      ) &&
      job.cancel_requested_at === null;
    const progress =
      latestAttempt?.progress_completed !== null &&
      latestAttempt?.progress_completed !== undefined &&
      latestAttempt.progress_total !== null
        ? (latestAttempt.progress_completed / latestAttempt.progress_total) *
          100
        : undefined;
    return (
      <article className="analysis-card frames-card" id="frames">
        <div className="analysis-card-heading">
          <h2>Frames</h2>
          <span className="status-pill">{stateLabel(job)}</span>
        </div>
        <p>
          {job?.public_failure_message ??
            latestAttempt?.progress_message ??
            "Uniformly sampled review frames will appear here."}
        </p>
        {job?.state === "running" ? (
          <div className="analysis-progress">
            <span>{latestAttempt?.progress_stage ?? "Extracting"}</span>
            <progress aria-label="Frames progress" max={100} value={progress} />
          </div>
        ) : null}
        {canCancel ? (
          <button
            className="button button-secondary"
            type="button"
            disabled={cancelPendingJobId === job.id}
            onClick={() => onCancel(job.id)}
          >
            {cancelPendingJobId === job.id ? "Canceling…" : "Cancel analysis"}
          </button>
        ) : null}
        {job !== undefined && ["failed", "canceled"].includes(job.state) ? (
          <button
            className="button button-secondary"
            type="button"
            disabled={retryPendingJobId === job.id}
            onClick={() => onRetry(job.id)}
          >
            {retryPendingJobId === job.id ? "Retrying…" : "Retry analysis"}
          </button>
        ) : null}
        {job?.diagnostic_id === null ||
        job?.diagnostic_id === undefined ? null : (
          <small className="diagnostic-reference">
            Error reference: {job.diagnostic_id}
          </small>
        )}
      </article>
    );
  }

  return (
    <article className="analysis-card frames-card" id="frames">
      <div className="analysis-card-heading">
        <div>
          <p className="card-eyebrow">Source-linked evidence</p>
          <h2>Frames</h2>
        </div>
        <span className="status-pill status-pill-ready">
          {frames.length} frames
        </span>
      </div>
      <div className="frame-preview-grid">
        {frames.slice(0, 6).map((frame) => (
          <FrameFigure
            artifact={frame.artifact}
            item={frame.item}
            jobId={job.id}
            key={frame.artifact.id}
            projectId={projectId}
          />
        ))}
      </div>
      <button
        className="button button-secondary"
        type="button"
        disabled={frames.length === 0}
        onClick={() => setExpanded(true)}
      >
        Review all frames
      </button>
      {latestStitch === undefined ? null : (
        <p className="stitch-summary">
          Latest stitch: <strong>{stateLabel(latestStitch)}</strong>
        </p>
      )}
      <AnalysisProvenance artifacts={artifactList} job={job} />
      {expanded ? (
        <div className="frame-review-overlay" role="dialog" aria-modal="true">
          <section className="frame-review-surface">
            <header>
              <div>
                <p className="card-eyebrow">Source-linked evidence</p>
                <h2>Extracted frames</h2>
                <p>{frames.length} uniformly sampled frames</p>
              </div>
              <button
                className="button button-secondary"
                type="button"
                onClick={() => setExpanded(false)}
              >
                Close
              </button>
            </header>
            <section
              className="stitch-controls"
              aria-labelledby="stitch-heading"
            >
              <div>
                <p className="card-eyebrow">Explicit analysis</p>
                <h3 id="stitch-heading">Create a panorama</h3>
                <p>
                  Select 2–12 overlapping frames in the order they should be
                  stitched. Selection starts a job only when you press the
                  button.
                </p>
              </div>
              <div className="stitch-actions">
                <span>{selectedOutputNames.length} selected</span>
                <button
                  className="button button-secondary"
                  type="button"
                  disabled={selectedOutputNames.length === 0}
                  onClick={() => setSelectedOutputNames([])}
                >
                  Clear
                </button>
                <button
                  className="button button-primary"
                  type="button"
                  disabled={
                    readOnly ||
                    selectedOutputNames.length < 2 ||
                    createStitch.isPending
                  }
                  onClick={() =>
                    createStitch.mutate({
                      projectId,
                      data: { selected_output_names: selectedOutputNames },
                    })
                  }
                >
                  {createStitch.isPending
                    ? "Creating…"
                    : "Stitch selected frames"}
                </button>
              </div>
              {readOnly ? (
                <p className="form-hint">
                  Restore this project to start a new stitch.
                </p>
              ) : null}
              {stitchError === undefined ? null : (
                <p className="form-error" role="alert">
                  {stitchError}
                </p>
              )}
            </section>
            {latestStitch === undefined ? null : (
              <StitchResult
                cancelPendingJobId={cancelPendingJobId}
                job={latestStitch}
                onCancel={onCancel}
                onRetry={onRetry}
                projectId={projectId}
                retryPendingJobId={retryPendingJobId}
              />
            )}
            <div className="frame-review-grid">
              {frames.map((frame) => {
                const selectionIndex = selectedOutputNames.indexOf(
                  frame.item.outputName,
                );
                return (
                  <label
                    className={`frame-selection ${
                      selectionIndex >= 0 ? "frame-selection-active" : ""
                    }`}
                    key={frame.artifact.id}
                  >
                    <input
                      type="checkbox"
                      checked={selectionIndex >= 0}
                      disabled={
                        selectionIndex < 0 && selectedOutputNames.length >= 12
                      }
                      onChange={() => toggleSelection(frame.item.outputName)}
                      aria-label={`Select frame ${frame.item.ordinal} for stitching`}
                    />
                    {selectionIndex < 0 ? null : (
                      <span className="selection-order" aria-hidden="true">
                        {selectionIndex + 1}
                      </span>
                    )}
                    <FrameFigure
                      artifact={frame.artifact}
                      item={frame.item}
                      jobId={job.id}
                      projectId={projectId}
                    />
                  </label>
                );
              })}
            </div>
          </section>
        </div>
      ) : null}
    </article>
  );
}

function StitchResult({
  projectId,
  job,
  cancelPendingJobId,
  onCancel,
  retryPendingJobId,
  onRetry,
}: {
  projectId: string;
  job: AnalysisJobResponse;
  cancelPendingJobId: string | undefined;
  onCancel: (jobId: string) => void;
  retryPendingJobId: string | undefined;
  onRetry: (jobId: string) => void;
}) {
  const artifacts =
    useListProjectAnalysisArtifactsApiProjectsProjectIdAnalysesJobIdArtifactsGet(
      projectId,
      job.id,
      { query: { enabled: job.state === "succeeded", retry: false } },
    );
  const artifactList =
    artifacts.data?.status === 200 ? artifacts.data.data : [];
  const panorama = artifactList.find(
    (artifact) =>
      artifact.output_name === "panorama" && artifact.kind === "blob",
  );
  const latestAttempt = job.attempts.at(-1);
  const progress =
    latestAttempt?.progress_completed !== null &&
    latestAttempt?.progress_completed !== undefined &&
    latestAttempt.progress_total !== null
      ? (latestAttempt.progress_completed / latestAttempt.progress_total) * 100
      : undefined;
  const canCancel =
    ["waiting_for_dependencies", "ready", "running", "retry_wait"].includes(
      job.state,
    ) && job.cancel_requested_at === null;

  return (
    <section className="stitch-result" aria-labelledby="latest-stitch-heading">
      <div className="analysis-card-heading">
        <div>
          <p className="card-eyebrow">Latest requested result</p>
          <h3 id="latest-stitch-heading">Stitched panorama</h3>
        </div>
        <span
          className={`status-pill ${
            job.state === "succeeded"
              ? "status-pill-ready"
              : job.state === "failed" || job.state === "blocked"
                ? "status-pill-error"
                : ""
          }`}
        >
          {stateLabel(job)}
        </span>
      </div>
      {panorama === undefined ? null : (
        <img
          className="stitch-panorama"
          src={`/api/projects/${encodeURIComponent(projectId)}/analyses/${encodeURIComponent(job.id)}/artifacts/${encodeURIComponent(panorama.id)}/content`}
          alt="Panorama stitched from the selected video frames"
        />
      )}
      {job.state === "running" ? (
        <div className="analysis-progress">
          <span>
            {latestAttempt?.progress_message ?? "Stitching selected frames"}
          </span>
          <progress
            aria-label="Frame stitching progress"
            max={100}
            value={progress}
          />
        </div>
      ) : null}
      {job.public_failure_message === null ? null : (
        <p className="form-error" role="alert">
          {job.public_failure_message}
        </p>
      )}
      <div className="stitch-actions">
        {canCancel ? (
          <button
            className="button button-secondary"
            type="button"
            disabled={cancelPendingJobId === job.id}
            onClick={() => onCancel(job.id)}
          >
            {cancelPendingJobId === job.id ? "Canceling…" : "Cancel stitch"}
          </button>
        ) : null}
        {["failed", "canceled"].includes(job.state) ? (
          <button
            className="button button-secondary"
            type="button"
            disabled={retryPendingJobId === job.id}
            onClick={() => onRetry(job.id)}
          >
            {retryPendingJobId === job.id ? "Retrying…" : "Retry stitch"}
          </button>
        ) : null}
      </div>
      {job.state === "succeeded" ? (
        <AnalysisProvenance artifacts={artifactList} job={job} />
      ) : null}
    </section>
  );
}

function FrameFigure({
  artifact,
  item,
  jobId,
  projectId,
}: {
  artifact: AnalysisArtifactResponse;
  item: FrameIndexItem;
  jobId: string;
  projectId: string;
}) {
  const source = `/api/projects/${encodeURIComponent(projectId)}/analyses/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(artifact.id)}/content`;
  return (
    <figure className="frame-figure">
      <img
        alt={`Video frame at ${formatTimestamp(item.timestampSeconds)}`}
        loading="lazy"
        src={source}
      />
      <figcaption>
        <span>Frame {item.ordinal}</span>
        <time>{formatTimestamp(item.timestampSeconds)}</time>
      </figcaption>
    </figure>
  );
}

function parseFrameIndex(value: unknown): FrameIndexItem[] {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    return [];
  const frames = (value as Record<string, unknown>).frames;
  if (!Array.isArray(frames)) return [];
  return frames.flatMap((candidate) => {
    if (
      typeof candidate !== "object" ||
      candidate === null ||
      Array.isArray(candidate)
    )
      return [];
    const record = candidate as Record<string, unknown>;
    if (
      typeof record.output_name !== "string" ||
      typeof record.ordinal !== "number" ||
      typeof record.timestamp_seconds !== "number"
    )
      return [];
    return [
      {
        outputName: record.output_name,
        ordinal: record.ordinal,
        timestampSeconds: record.timestamp_seconds,
      },
    ];
  });
}

function formatTimestamp(seconds: number): string {
  const wholeSeconds = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(wholeSeconds / 3600);
  const minutes = Math.floor((wholeSeconds % 3600) / 60);
  const remainder = wholeSeconds % 60;
  return [hours, minutes, remainder]
    .map((part) => part.toString().padStart(2, "0"))
    .join(":");
}

function stateLabel(job: AnalysisJobResponse | undefined): string {
  if (job === undefined) return "Waiting for analysis";
  if (job.state === "running" && job.cancel_requested_at !== null)
    return "Canceling";
  const labels: Record<string, string> = {
    waiting_for_dependencies: "Waiting for dependencies",
    ready: "Queued",
    running: "Running",
    retry_wait: "Retry scheduled",
    failed: "Failed",
    blocked: "Blocked",
    canceled: "Canceled",
  };
  return labels[job.state] ?? job.state.replaceAll("_", " ");
}
