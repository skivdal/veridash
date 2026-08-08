import { useQuery } from "@tanstack/react-query";

import {
  getStreamProjectAnalysisArtifactApiProjectsProjectIdAnalysesJobIdArtifactsArtifactIdContentGetQueryKey,
  getStreamProjectAnalysisArtifactApiProjectsProjectIdAnalysesJobIdArtifactsArtifactIdContentGetUrl,
  useListProjectAnalysisArtifactsApiProjectsProjectIdAnalysesJobIdArtifactsGet,
} from "../../api/generated/client";
import type { AnalysisJobResponse } from "../../api/generated/schemas";
import { AnalysisProvenance } from "./AnalysisProvenance";

interface TranscriptSegment {
  ordinal: number;
  start_seconds: number;
  end_seconds: number;
  text: string;
}

interface TranscriptDocument {
  detected_language: string;
  detected_language_probability: number;
  inference_device: string;
  inference_compute_type: string;
  segments: TranscriptSegment[];
}

interface TranscriptCardProps {
  projectId: string;
  job: AnalysisJobResponse | undefined;
  cancelPendingJobId: string | undefined;
  onCancel: (jobId: string) => void;
  retryPendingJobId: string | undefined;
  onRetry: (jobId: string) => void;
}

export function TranscriptCard({
  projectId,
  job,
  cancelPendingJobId,
  onCancel,
  retryPendingJobId,
  onRetry,
}: TranscriptCardProps) {
  const artifacts =
    useListProjectAnalysisArtifactsApiProjectsProjectIdAnalysesJobIdArtifactsGet(
      projectId,
      job?.id ?? "",
      { query: { enabled: job?.state === "succeeded", retry: false } },
    );
  const artifact =
    artifacts.data?.status === 200
      ? artifacts.data.data.find(
          (candidate) => candidate.output_name === "transcript",
        )
      : undefined;
  const transcript = useQuery({
    queryKey:
      getStreamProjectAnalysisArtifactApiProjectsProjectIdAnalysesJobIdArtifactsArtifactIdContentGetQueryKey(
        projectId,
        job?.id ?? "",
        artifact?.id ?? "",
      ),
    enabled: job?.state === "succeeded" && artifact !== undefined,
    retry: false,
    queryFn: async ({ signal }) => {
      if (job === undefined || artifact === undefined)
        throw new Error("Transcript artifact is unavailable");
      const response = await fetch(
        getStreamProjectAnalysisArtifactApiProjectsProjectIdAnalysesJobIdArtifactsArtifactIdContentGetUrl(
          projectId,
          job.id,
          artifact.id,
        ),
        { credentials: "same-origin", signal },
      );
      if (!response.ok)
        throw new Error("Transcript artifact could not be loaded");
      return parseTranscript((await response.json()) as unknown);
    },
  });

  if (job?.state !== "succeeded" || transcript.data === undefined) {
    const latestAttempt = job?.attempts.at(-1);
    const canCancel =
      job !== undefined &&
      ["waiting_for_dependencies", "ready", "running", "retry_wait"].includes(
        job.state,
      ) &&
      job.cancel_requested_at === null;
    const progress = progressPercent(job);
    return (
      <article className="analysis-card" id="transcribe">
        <div className="analysis-card-heading">
          <h2>Transcription &amp; Translation</h2>
          <span className="status-pill">{jobStatus(job)}</span>
        </div>
        <p>
          {job?.public_failure_message ??
            latestAttempt?.progress_message ??
            (transcript.isError
              ? "The completed transcript could not be loaded."
              : "Timestamped source-language speech will appear here. Translation remains a separate future analysis.")}
        </p>
        {job?.state === "running" ? (
          <div className="analysis-progress">
            <span>{latestAttempt?.progress_stage ?? "Working"}</span>
            <progress
              aria-label="Transcription progress"
              max={100}
              value={progress}
            />
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
    <article className="analysis-card transcript-card" id="transcribe">
      <div className="analysis-card-heading">
        <div>
          <p className="card-eyebrow">Original speech</p>
          <h2>Transcription &amp; Translation</h2>
        </div>
        <span className="status-pill status-pill-ready">Complete</span>
      </div>
      <dl className="transcript-facts">
        <div>
          <dt>Detected language</dt>
          <dd>{languageName(transcript.data.detected_language)}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>
            {Math.round(transcript.data.detected_language_probability * 100)}%
          </dd>
        </div>
      </dl>
      {transcript.data.segments.length === 0 ? (
        <p>No speech segments were detected.</p>
      ) : (
        <ol
          className="transcript-segments"
          aria-label={`${transcript.data.segments.length} timestamped transcript segments`}
        >
          {transcript.data.segments.map((segment) => (
            <TranscriptRow key={segment.ordinal} segment={segment} />
          ))}
        </ol>
      )}
      <p className="evidence-caveat">
        This is machine transcription, not a verified quotation. Check important
        passages against the source video. No summary or interpretation is
        generated.
      </p>
      <p className="translation-pending">
        Translation has not run; the source-language transcript is preserved
        independently.
      </p>
      <AnalysisProvenance
        artifacts={artifacts.data?.status === 200 ? artifacts.data.data : []}
        job={job}
      />
    </article>
  );
}

function TranscriptRow({ segment }: { segment: TranscriptSegment }) {
  return (
    <li>
      <time>{formatTimestamp(segment.start_seconds)}</time>
      <span>{segment.text.length === 0 ? "[No text]" : segment.text}</span>
    </li>
  );
}

function parseTranscript(value: unknown): TranscriptDocument {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    throw new Error("Transcript document is invalid");
  const candidate = value as Partial<TranscriptDocument>;
  if (
    typeof candidate.detected_language !== "string" ||
    typeof candidate.detected_language_probability !== "number" ||
    typeof candidate.inference_device !== "string" ||
    typeof candidate.inference_compute_type !== "string" ||
    !Array.isArray(candidate.segments) ||
    !candidate.segments.every(isTranscriptSegment)
  ) {
    throw new Error("Transcript document is invalid");
  }
  return candidate as TranscriptDocument;
}

function isTranscriptSegment(value: unknown): value is TranscriptSegment {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    return false;
  const segment = value as Partial<TranscriptSegment>;
  return (
    typeof segment.ordinal === "number" &&
    typeof segment.start_seconds === "number" &&
    typeof segment.end_seconds === "number" &&
    typeof segment.text === "string"
  );
}

function progressPercent(job: AnalysisJobResponse | undefined) {
  const attempt = job?.attempts.at(-1);
  if (
    attempt?.progress_completed === null ||
    attempt?.progress_completed === undefined ||
    attempt.progress_total === null
  )
    return undefined;
  return Math.min(
    100,
    (attempt.progress_completed / attempt.progress_total) * 100,
  );
}

function jobStatus(job: AnalysisJobResponse | undefined): string {
  if (job === undefined) return "Waiting for analysis";
  if (job.state === "running" && job.cancel_requested_at !== null)
    return "Canceling";
  const labels: Record<string, string> = {
    waiting_for_dependencies: "Waiting for dependencies",
    ready: "Queued for GPU worker",
    running: "Running",
    retry_wait: "Retry scheduled",
    succeeded: "Complete",
    failed: "Failed",
    blocked: "Blocked",
    canceled: "Canceled",
  };
  return labels[job.state] ?? job.state.replaceAll("_", " ");
}

function formatTimestamp(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const remainder = whole % 60;
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`
    : `${minutes}:${String(remainder).padStart(2, "0")}`;
}

function languageName(code: string): string {
  try {
    return `${new Intl.DisplayNames(undefined, { type: "language" }).of(code) ?? code} (${code})`;
  } catch {
    return code;
  }
}
