import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

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

interface TranslationDocument {
  source_language: string;
  target_language: "en";
  status: "translated" | "not_applicable" | "no_content";
  segments: TranscriptSegment[];
}

interface TranscriptCardProps {
  projectId: string;
  job: AnalysisJobResponse | undefined;
  translationJob: AnalysisJobResponse | undefined;
  cancelPendingJobId: string | undefined;
  onCancel: (jobId: string) => void;
  retryPendingJobId: string | undefined;
  onRetry: (jobId: string) => void;
}

export function TranscriptCard({
  projectId,
  job,
  translationJob,
  cancelPendingJobId,
  onCancel,
  retryPendingJobId,
  onRetry,
}: TranscriptCardProps) {
  const [visibleLanguage, setVisibleLanguage] = useState<
    "original" | "english"
  >("original");
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
  const translationArtifacts =
    useListProjectAnalysisArtifactsApiProjectsProjectIdAnalysesJobIdArtifactsGet(
      projectId,
      translationJob?.id ?? "",
      {
        query: {
          enabled: translationJob?.state === "succeeded",
          retry: false,
        },
      },
    );
  const translationArtifact =
    translationArtifacts.data?.status === 200
      ? translationArtifacts.data.data.find(
          (candidate) => candidate.output_name === "translation",
        )
      : undefined;
  const translation = useQuery({
    queryKey:
      getStreamProjectAnalysisArtifactApiProjectsProjectIdAnalysesJobIdArtifactsArtifactIdContentGetQueryKey(
        projectId,
        translationJob?.id ?? "",
        translationArtifact?.id ?? "",
      ),
    enabled:
      translationJob?.state === "succeeded" &&
      translationArtifact !== undefined,
    retry: false,
    queryFn: async ({ signal }) => {
      if (translationJob === undefined || translationArtifact === undefined)
        throw new Error("Translation artifact is unavailable");
      const response = await fetch(
        getStreamProjectAnalysisArtifactApiProjectsProjectIdAnalysesJobIdArtifactsArtifactIdContentGetUrl(
          projectId,
          translationJob.id,
          translationArtifact.id,
        ),
        { credentials: "same-origin", signal },
      );
      if (!response.ok)
        throw new Error("Translation artifact could not be loaded");
      return parseTranslation((await response.json()) as unknown);
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

  const englishSegments =
    translation.data?.status === "translated"
      ? translation.data.segments
      : undefined;
  const hasEnglishTranslation = englishSegments !== undefined;
  const visibleSegments =
    visibleLanguage === "english" && hasEnglishTranslation
      ? englishSegments
      : transcript.data.segments;

  return (
    <article className="analysis-card transcript-card" id="transcribe">
      <div className="analysis-card-heading">
        <div>
          <p className="card-eyebrow">
            {visibleLanguage === "english" && hasEnglishTranslation
              ? "English translation"
              : "Original speech"}
          </p>
          <h2>Transcription &amp; Translation</h2>
        </div>
        <span className="status-pill status-pill-ready">
          {translation.data === undefined ? "Transcript ready" : "Complete"}
        </span>
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
      {hasEnglishTranslation ? (
        <fieldset className="transcript-language-switch">
          <legend className="visually-hidden">Transcript language</legend>
          <button
            className={visibleLanguage === "original" ? "is-active" : undefined}
            type="button"
            aria-pressed={visibleLanguage === "original"}
            onClick={() => setVisibleLanguage("original")}
          >
            Original
          </button>
          <button
            className={visibleLanguage === "english" ? "is-active" : undefined}
            type="button"
            aria-pressed={visibleLanguage === "english"}
            onClick={() => setVisibleLanguage("english")}
          >
            English
          </button>
        </fieldset>
      ) : null}
      {visibleSegments.length === 0 ? (
        <p>No speech segments were detected.</p>
      ) : (
        <ol
          className="transcript-segments"
          aria-label={`${visibleSegments.length} timestamped transcript segments`}
        >
          {visibleSegments.map((segment) => (
            <TranscriptRow key={segment.ordinal} segment={segment} />
          ))}
        </ol>
      )}
      <p className="evidence-caveat">
        This is machine transcription, not a verified quotation. Check important
        passages against the source video. No summary or interpretation is
        generated.
      </p>
      <TranslationStatus
        job={translationJob}
        document={translation.data}
        loadFailed={translation.isError}
        cancelPendingJobId={cancelPendingJobId}
        onCancel={onCancel}
        retryPendingJobId={retryPendingJobId}
        onRetry={onRetry}
      />
      <AnalysisProvenance
        artifacts={artifacts.data?.status === 200 ? artifacts.data.data : []}
        job={job}
      />
      {translationJob?.state === "succeeded" ? (
        <AnalysisProvenance
          artifacts={
            translationArtifacts.data?.status === 200
              ? translationArtifacts.data.data
              : []
          }
          job={translationJob}
        />
      ) : null}
    </article>
  );
}

function TranslationStatus({
  job,
  document,
  loadFailed,
  cancelPendingJobId,
  onCancel,
  retryPendingJobId,
  onRetry,
}: {
  job: AnalysisJobResponse | undefined;
  document: TranslationDocument | undefined;
  loadFailed: boolean;
  cancelPendingJobId: string | undefined;
  onCancel: (jobId: string) => void;
  retryPendingJobId: string | undefined;
  onRetry: (jobId: string) => void;
}) {
  if (document?.status === "translated") {
    return (
      <p className="translation-pending">
        English translation is ready. The original transcript remains unchanged.
      </p>
    );
  }
  if (document?.status === "not_applicable") {
    return (
      <p className="translation-pending">
        The detected speech is already English; no provider translation was
        needed.
      </p>
    );
  }
  if (document?.status === "no_content") {
    return (
      <p className="translation-pending">
        No speech required translation, so the provider was not contacted.
      </p>
    );
  }

  const canCancel =
    job !== undefined &&
    ["waiting_for_dependencies", "ready", "running", "retry_wait"].includes(
      job.state,
    ) &&
    job.cancel_requested_at === null;
  const attempt = job?.attempts.at(-1);
  return (
    <div className="translation-pending translation-status">
      <p>
        {job?.public_failure_message ??
          attempt?.progress_message ??
          (loadFailed
            ? "The completed English translation could not be loaded."
            : job === undefined
              ? "English translation has not been scheduled."
              : `English translation: ${jobStatus(job)}.`)}
      </p>
      {job?.state === "running" ? (
        <div className="analysis-progress">
          <span>{attempt?.progress_stage ?? "Translating"}</span>
          <progress
            aria-label="Translation progress"
            max={100}
            value={progressPercent(job)}
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
          {cancelPendingJobId === job.id ? "Canceling…" : "Cancel translation"}
        </button>
      ) : null}
      {job !== undefined && ["failed", "canceled"].includes(job.state) ? (
        <button
          className="button button-secondary"
          type="button"
          disabled={retryPendingJobId === job.id}
          onClick={() => onRetry(job.id)}
        >
          {retryPendingJobId === job.id ? "Retrying…" : "Retry translation"}
        </button>
      ) : null}
      {job?.diagnostic_id ? (
        <small className="diagnostic-reference">
          Error reference: {job.diagnostic_id}
        </small>
      ) : null}
    </div>
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

function parseTranslation(value: unknown): TranslationDocument {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    throw new Error("Translation document is invalid");
  const candidate = value as Partial<TranslationDocument>;
  if (
    typeof candidate.source_language !== "string" ||
    candidate.target_language !== "en" ||
    !["translated", "not_applicable", "no_content"].includes(
      candidate.status ?? "",
    ) ||
    !Array.isArray(candidate.segments) ||
    !candidate.segments.every(isTranscriptSegment)
  ) {
    throw new Error("Translation document is invalid");
  }
  return candidate as TranslationDocument;
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
    attempt.progress_total === null ||
    attempt.progress_total <= 0
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
    ready:
      job.resource_class === "translation"
        ? "Queued for translation worker"
        : "Queued for GPU worker",
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
