import { useListProjectAnalysisArtifactsApiProjectsProjectIdAnalysesJobIdArtifactsGet } from "../../api/generated/client";
import type { AnalysisJobResponse } from "../../api/generated/schemas";

interface MetadataCardProps {
  projectId: string;
  job: AnalysisJobResponse | undefined;
  cancelPendingJobId: string | undefined;
  onCancel: (jobId: string) => void;
}

export function MetadataCard({
  projectId,
  job,
  cancelPendingJobId,
  onCancel,
}: MetadataCardProps) {
  const artifacts =
    useListProjectAnalysisArtifactsApiProjectsProjectIdAnalysesJobIdArtifactsGet(
      projectId,
      job?.id ?? "",
      { query: { enabled: job?.state === "succeeded", retry: false } },
    );
  const artifact =
    artifacts.data?.status === 200
      ? artifacts.data.data.find(
          (candidate) => candidate.output_name === "result",
        )
      : undefined;
  const result = asRecord(artifact?.json_payload);
  const probe = asRecord(result?.probe);
  const format = asRecord(probe?.format);
  const streams = Array.isArray(probe?.streams) ? probe.streams : [];
  const tags = asRecord(format?.tags);

  if (job?.state !== "succeeded" || artifact === undefined) {
    const latestAttempt = job?.attempts.at(-1);
    const status = job === undefined ? "Waiting for analysis" : stateLabel(job);
    const canCancel =
      job !== undefined &&
      ["waiting_for_dependencies", "ready", "running", "retry_wait"].includes(
        job.state,
      ) &&
      job.cancel_requested_at === null;
    return (
      <article className="analysis-card">
        <div className="analysis-card-heading">
          <h2>Metadata</h2>
          <span className="status-pill">{status}</span>
        </div>
        <p>
          {job?.public_failure_message ??
            latestAttempt?.progress_message ??
            "Container, stream, and embedded metadata will appear here."}
        </p>
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
      </article>
    );
  }

  return (
    <article className="analysis-card metadata-card">
      <div className="analysis-card-heading">
        <div>
          <p className="card-eyebrow">Raw source facts</p>
          <h2>Metadata</h2>
        </div>
        <span className="status-pill status-pill-ready">Complete</span>
      </div>
      <dl className="metadata-facts">
        <div>
          <dt>Container</dt>
          <dd>
            {displayValue(format?.format_long_name ?? format?.format_name)}
          </dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd>{formatDuration(format?.duration)}</dd>
        </div>
        <div>
          <dt>Streams</dt>
          <dd>{streams.length}</dd>
        </div>
        <div>
          <dt>Embedded tags</dt>
          <dd>{tags === undefined ? 0 : Object.keys(tags).length}</dd>
        </div>
      </dl>
      <ul className="metadata-streams" aria-label="Media streams">
        {streams.map((stream) => {
          const value = asRecord(stream);
          return (
            <li key={displayValue(value?.index)}>
              <strong>{displayValue(value?.codec_type, "Stream")}</strong>
              <span>
                {displayValue(value?.codec_long_name ?? value?.codec_name)}
              </span>
            </li>
          );
        })}
      </ul>
      <details>
        <summary>Inspect raw FFprobe result</summary>
        <pre className="metadata-raw">{JSON.stringify(probe, null, 2)}</pre>
      </details>
    </article>
  );
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function displayValue(value: unknown, fallback = "Not reported"): string {
  return typeof value === "string" || typeof value === "number"
    ? String(value)
    : fallback;
}

function formatDuration(value: unknown): string {
  if (typeof value !== "string" && typeof value !== "number")
    return "Not reported";
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) return "Not reported";
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0")}`;
}

function stateLabel(job: AnalysisJobResponse): string {
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
