import { useState } from "react";

import { useListProjectAnalysisArtifactsApiProjectsProjectIdAnalysesJobIdArtifactsGet } from "../../api/generated/client";
import type { AnalysisJobResponse } from "../../api/generated/schemas";
import { AnalysisProvenance } from "./AnalysisProvenance";

interface MapCardProps {
  projectId: string;
  job: AnalysisJobResponse | undefined;
  cancelPendingJobId: string | undefined;
  onCancel: (jobId: string) => void;
  retryPendingJobId: string | undefined;
  onRetry: (jobId: string) => void;
}

export function MapCard({
  projectId,
  job,
  cancelPendingJobId,
  onCancel,
  retryPendingJobId,
  onRetry,
}: MapCardProps) {
  const [mapRequested, setMapRequested] = useState(false);
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
  const latitude = finiteNumber(result?.latitude);
  const longitude = finiteNumber(result?.longitude);
  const status = typeof result?.status === "string" ? result.status : undefined;

  if (job?.state !== "succeeded" || artifact === undefined) {
    const latestAttempt = job?.attempts.at(-1);
    const canCancel =
      job !== undefined &&
      ["waiting_for_dependencies", "ready", "running", "retry_wait"].includes(
        job.state,
      ) &&
      job.cancel_requested_at === null;
    return (
      <article className="analysis-card map-card">
        <div className="analysis-card-heading">
          <h2>Map</h2>
          <span className="status-pill">{stateLabel(job)}</span>
        </div>
        <p>
          {job?.public_failure_message ??
            latestAttempt?.progress_message ??
            "Explicit embedded coordinates will appear here after metadata inspection."}
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
      </article>
    );
  }

  if (status !== "found" || latitude === undefined || longitude === undefined) {
    const descriptions: Record<string, string> = {
      not_found:
        "No supported embedded GPS coordinate tag was present. This says nothing about where the video was recorded.",
      invalid:
        "A location-like metadata tag was present, but it was not an unambiguous signed decimal coordinate.",
      ambiguous:
        "The source contains conflicting embedded coordinates, so VeriDash did not choose one.",
    };
    return (
      <article className="analysis-card map-card">
        <div className="analysis-card-heading">
          <div>
            <p className="card-eyebrow">Embedded metadata only</p>
            <h2>Map</h2>
          </div>
          <span className="status-pill status-pill-ready">Inspected</span>
        </div>
        <p>{descriptions[status ?? ""] ?? "No map coordinate is available."}</p>
        <AnalysisProvenance
          artifacts={artifacts.data?.status === 200 ? artifacts.data.data : []}
          job={job}
        />
      </article>
    );
  }

  const bbox = mapBoundingBox(latitude, longitude);
  const mapUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${encodeURIComponent(`${latitude},${longitude}`)}`;
  const streetViewUrl = `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${encodeURIComponent(`${latitude},${longitude}`)}`;
  return (
    <article className="analysis-card map-card map-card-found">
      <div className="analysis-card-heading">
        <div>
          <p className="card-eyebrow">Embedded metadata only</p>
          <h2>Map</h2>
        </div>
        <span className="status-pill status-pill-ready">Coordinate found</span>
      </div>
      <p className="coordinate-readout">
        {formatCoordinate(latitude, "N", "S")},{" "}
        {formatCoordinate(longitude, "E", "W")}
      </p>
      {mapRequested ? (
        <iframe
          className="embedded-map"
          src={mapUrl}
          title={`OpenStreetMap around ${latitude}, ${longitude}`}
          loading="lazy"
          referrerPolicy="no-referrer"
        />
      ) : (
        <div className="map-consent">
          <p>Loading the map sends these coordinates to OpenStreetMap.</p>
          <button
            className="button button-secondary"
            type="button"
            onClick={() => setMapRequested(true)}
          >
            Load map
          </button>
        </div>
      )}
      <a
        className="button button-primary"
        href={streetViewUrl}
        target="_blank"
        rel="noreferrer"
      >
        Open Google Street View
      </a>
      <p className="evidence-caveat">
        Embedded coordinates can be missing or altered; they are evidence to
        inspect, not proof of capture location.
      </p>
      <AnalysisProvenance
        artifacts={artifacts.data?.status === 200 ? artifacts.data.data : []}
        job={job}
      />
    </article>
  );
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function finiteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : undefined;
}

function formatCoordinate(
  value: number,
  positive: string,
  negative: string,
): string {
  return `${Math.abs(value).toFixed(6)}° ${value < 0 ? negative : positive}`;
}

function mapBoundingBox(latitude: number, longitude: number): string {
  const latitudeDelta = 0.015;
  const longitudeDelta = 0.025;
  return [
    longitude - longitudeDelta,
    latitude - latitudeDelta,
    longitude + longitudeDelta,
    latitude + latitudeDelta,
  ].join(",");
}

function stateLabel(job: AnalysisJobResponse | undefined): string {
  if (job === undefined) return "Waiting for analysis";
  if (job.state === "running" && job.cancel_requested_at !== null)
    return "Canceling";
  const labels: Record<string, string> = {
    waiting_for_dependencies: "Waiting for metadata",
    ready: "Queued",
    running: "Running",
    retry_wait: "Retry scheduled",
    failed: "Failed",
    blocked: "Blocked",
    canceled: "Canceled",
  };
  return labels[job.state] ?? job.state.replaceAll("_", " ");
}
