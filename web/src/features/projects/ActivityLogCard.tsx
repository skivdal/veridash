import { useState } from "react";

import { useListProjectEventLogApiProjectsProjectIdEventLogGet } from "../../api/generated/client";
import type {
  AnalysisJobResponse,
  ProjectEventResponse,
} from "../../api/generated/schemas";

export function ActivityLogCard({
  projectId,
  jobs,
}: {
  projectId: string;
  jobs: AnalysisJobResponse[];
}) {
  const [showProgress, setShowProgress] = useState(false);
  const events = useListProjectEventLogApiProjectsProjectIdEventLogGet(
    projectId,
    { limit: 250 },
    { query: { retry: false } },
  );
  const jobNames = new Map(jobs.map((job) => [job.id, job.display_name]));
  const visibleEvents =
    events.data?.status === 200
      ? [...events.data.data]
          .reverse()
          .filter(
            (event) => showProgress || event.event_type !== "job.progress",
          )
      : [];

  return (
    <article className="analysis-card activity-card" id="activity">
      <div className="analysis-card-heading">
        <div>
          <p className="card-eyebrow">Durable server journal</p>
          <h2>Activity log</h2>
        </div>
        <span className="status-pill">
          {events.data?.status === 200
            ? `${events.data.data.length} events`
            : "Loading"}
        </span>
      </div>
      <p>
        Requested work and timestamped server updates. Raw operator diagnostics
        are excluded; failures use their audit-safe message and reference.
      </p>
      <label className="activity-progress-filter">
        <input
          type="checkbox"
          checked={showProgress}
          onChange={(event) => setShowProgress(event.target.checked)}
        />
        Show progress updates
      </label>
      {events.isError ? (
        <p className="form-error" role="alert">
          The activity log could not be loaded.
        </p>
      ) : visibleEvents.length === 0 ? (
        <p>No matching activity has been recorded yet.</p>
      ) : (
        <ol className="activity-log">
          {visibleEvents.map((event) => (
            <li key={event.id}>
              <time dateTime={event.created_at}>
                {formatEventTime(event.created_at)}
              </time>
              <div>
                <strong>{describeEvent(event, jobNames)}</strong>
                <small>
                  #{event.id} · {event.source}
                </small>
                <details>
                  <summary>Event details</summary>
                  <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                </details>
              </div>
            </li>
          ))}
        </ol>
      )}
      {events.data?.status === 200 && events.data.data.length === 250 ? (
        <small className="activity-limit-note">
          Showing the latest 250 events. Progress entries can be hidden above.
        </small>
      ) : null}
    </article>
  );
}

function describeEvent(
  event: ProjectEventResponse,
  jobNames: Map<string, string>,
): string {
  const payload = asRecord(event.payload);
  const moduleName =
    (event.job_id === null ? undefined : jobNames.get(event.job_id)) ??
    displayValue(payload?.module_id, "Analysis");
  switch (event.event_type) {
    case "job.created":
      return `Requested ${moduleName}`;
    case "job.progress": {
      const progress =
        typeof payload?.completed === "number" &&
        typeof payload?.total === "number"
          ? ` (${payload.completed}/${payload.total})`
          : "";
      return `${moduleName}: ${displayValue(payload?.message ?? payload?.stage, "progress update")}${progress}`;
    }
    case "job.state_changed":
      return `${moduleName}: ${displayValue(payload?.state, "state changed").replaceAll("_", " ")}`;
    case "job.error":
      return `${moduleName}: ${displayValue(payload?.message, "analysis failed")}`;
    case "job.retry_requested":
      return `Retry requested for ${moduleName}`;
    case "job.cancel_requested":
      return `Cancellation requested for ${moduleName}`;
    case "media.uploaded":
      return "Source video uploaded; automatic analyses requested";
    case "media.failed":
      return "Source video validation failed";
    case "project.note_updated":
      return `Notes saved at revision ${displayValue(payload?.revision, "unknown")}`;
    case "project.updated":
      return "Project details updated";
    default:
      return event.event_type.replaceAll("_", " ").replaceAll(".", " · ");
  }
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function displayValue(value: unknown, fallback: string): string {
  return typeof value === "string" || typeof value === "number"
    ? String(value)
    : fallback;
}

function formatEventTime(value: string): string {
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.valueOf()) ? value : timestamp.toLocaleString();
}
