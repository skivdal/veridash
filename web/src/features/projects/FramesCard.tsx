import { useState } from "react";

import { useListProjectAnalysisArtifactsApiProjectsProjectIdAnalysesJobIdArtifactsGet } from "../../api/generated/client";
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
}: FramesCardProps) {
  const [expanded, setExpanded] = useState(false);
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
      <article className="analysis-card frames-card">
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
    <article className="analysis-card frames-card">
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
            <div className="frame-review-grid">
              {frames.map((frame) => (
                <FrameFigure
                  artifact={frame.artifact}
                  item={frame.item}
                  jobId={job.id}
                  key={frame.artifact.id}
                  projectId={projectId}
                />
              ))}
            </div>
          </section>
        </div>
      ) : null}
    </article>
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
