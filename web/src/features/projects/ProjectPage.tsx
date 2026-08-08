import { useQueryClient } from "@tanstack/react-query";
import { Link, Navigate } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";

import { ApiError } from "../../api/fetcher";
import {
  getGetProjectApiProjectsProjectIdGetQueryKey,
  getListProjectAnalysesApiProjectsProjectIdAnalysesGetQueryKey,
  getListProjectsApiProjectsGetQueryKey,
  useArchiveProjectApiProjectsProjectIdArchivePost,
  useCancelProjectAnalysisApiProjectsProjectIdAnalysesJobIdCancelPost,
  useGetCurrentUserApiAuthMeGet,
  useGetProjectApiProjectsProjectIdGet,
  useListProjectAnalysesApiProjectsProjectIdAnalysesGet,
  useRenameProjectApiProjectsProjectIdPatch,
  useRestoreProjectApiProjectsProjectIdRestorePost,
} from "../../api/generated/client";
import type { AnalysisJobResponse } from "../../api/generated/schemas";
import { AppHeader } from "../../components/AppHeader";
import { SourceMediaPanel } from "../source-media/SourceMediaPanel";
import { useProjectEvents } from "./projectEvents";

const modulePlaceholders = [
  [
    "Metadata",
    "Container, stream, and embedded metadata will appear here.",
    "probe_media",
  ],
  [
    "Frames",
    "Extracted frames and stitching controls will appear here.",
    "extract_keyframes",
  ],
  [
    "Transcription",
    "Timestamped source-language transcription will appear here.",
    "transcribe",
  ],
  [
    "Object Detection",
    "Detected objects will remain linked to source frames.",
    "detect_objects",
  ],
  [
    "Map",
    "Verified embedded coordinates can be inspected here.",
    "extract_coordinates",
  ],
] as const;
const moduleNames = ["Source", ...modulePlaceholders.map(([name]) => name)];

interface ProjectPageProps {
  projectId: string;
}

export function ProjectPage({ projectId }: ProjectPageProps) {
  const queryClient = useQueryClient();
  const [isRenaming, setIsRenaming] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const currentUser = useGetCurrentUserApiAuthMeGet({
    query: { retry: false },
  });
  const project = useGetProjectApiProjectsProjectIdGet(projectId, {
    query: { enabled: currentUser.isSuccess, retry: false },
  });
  const analyses = useListProjectAnalysesApiProjectsProjectIdAnalysesGet(
    projectId,
    {
      query: {
        enabled: project.isSuccess,
        retry: false,
        refetchInterval: (query) => {
          if (typeof EventSource !== "undefined") return false;
          const response = query.state.data;
          if (response?.status !== 200) return false;
          return response.data.some((job) => !isTerminalJobState(job.state))
            ? 3_000
            : false;
        },
      },
    },
  );
  useProjectEvents(projectId, queryClient, project.isSuccess);
  const sessionData =
    currentUser.data?.status === 200 ? currentUser.data.data : undefined;
  const projectData =
    project.data?.status === 200 ? project.data.data : undefined;
  const analysisJobs = analyses.data?.status === 200 ? analyses.data.data : [];
  const updateCachedProject = async (response: unknown) => {
    const candidate = response as { status?: number };
    if (candidate.status !== 200) return;
    queryClient.setQueryData(
      getGetProjectApiProjectsProjectIdGetQueryKey(projectId),
      response,
    );
    await queryClient.invalidateQueries({
      queryKey: getListProjectsApiProjectsGetQueryKey(),
    });
  };
  const renameProject = useRenameProjectApiProjectsProjectIdPatch({
    mutation: {
      onSuccess: async (response) => {
        await updateCachedProject(response);
        setIsRenaming(false);
      },
    },
  });
  const archiveProject = useArchiveProjectApiProjectsProjectIdArchivePost({
    mutation: { onSuccess: updateCachedProject },
  });
  const restoreProject = useRestoreProjectApiProjectsProjectIdRestorePost({
    mutation: { onSuccess: updateCachedProject },
  });
  const cancelAnalysis =
    useCancelProjectAnalysisApiProjectsProjectIdAnalysesJobIdCancelPost({
      mutation: {
        onSuccess: async () => {
          await queryClient.invalidateQueries({
            queryKey:
              getListProjectAnalysesApiProjectsProjectIdAnalysesGetQueryKey(
                projectId,
              ),
          });
        },
      },
    });

  if (
    currentUser.error instanceof ApiError &&
    currentUser.error.status === 401
  ) {
    return <Navigate to="/login" replace />;
  }

  if (project.error instanceof ApiError && project.error.status === 401) {
    return <Navigate to="/login" replace />;
  }

  if (currentUser.isError) {
    return (
      <div className="app-canvas">
        <AppHeader />
        <main className="page-shell">
          <section className="status-card">
            <h1>Unable to check your session</h1>
            <p>The server could not confirm your sign-in state.</p>
            <button
              className="button button-primary"
              type="button"
              onClick={() => currentUser.refetch()}
            >
              Try again
            </button>
          </section>
        </main>
      </div>
    );
  }

  if (currentUser.isPending || project.isPending) {
    return <LoadingScreen label="Loading project…" />;
  }

  if (project.error instanceof ApiError) {
    return (
      <div className="app-canvas">
        <AppHeader username={sessionData?.user.username} />
        <main className="page-shell page-shell-top">
          <section className="status-card">
            <p className="eyebrow">Project unavailable</p>
            <h1>
              {project.error.status === 404
                ? "Project not found"
                : "Unable to load project"}
            </h1>
            <p className="intro-copy">{project.error.message}</p>
            <Link className="button button-primary" to="/projects">
              Back to projects
            </Link>
          </section>
        </main>
      </div>
    );
  }

  if (sessionData === undefined || projectData === undefined) return null;

  function submitRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    renameProject.mutate({ projectId, data: { title: draftTitle } });
  }

  const mutationError =
    renameProject.error instanceof ApiError
      ? renameProject.error.message
      : archiveProject.error instanceof ApiError
        ? archiveProject.error.message
        : restoreProject.error instanceof ApiError
          ? restoreProject.error.message
          : cancelAnalysis.error instanceof ApiError
            ? cancelAnalysis.error.message
            : undefined;
  const lifecycleMutationPending =
    archiveProject.isPending || restoreProject.isPending;

  return (
    <div className="app-canvas">
      <AppHeader username={sessionData.user.username} />
      <main className="workspace-shell">
        <div className="workspace-heading">
          <div>
            <Link className="back-link" to="/projects">
              ← All projects
            </Link>
            <h1>{projectData.title}</h1>
            <p className="workspace-meta">
              Saved project · {projectData.state}
            </p>
          </div>
          <div className="workspace-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => {
                setDraftTitle(projectData.title);
                renameProject.reset();
                setIsRenaming((visible) => !visible);
              }}
            >
              {isRenaming ? "Cancel rename" : "Rename"}
            </button>
            {projectData.state === "archived" ? (
              <button
                className="button button-secondary"
                type="button"
                disabled={lifecycleMutationPending}
                onClick={() => restoreProject.mutate({ projectId })}
              >
                {restoreProject.isPending ? "Restoring…" : "Restore project"}
              </button>
            ) : (
              <button
                className="button button-secondary"
                type="button"
                disabled={lifecycleMutationPending}
                onClick={() => archiveProject.mutate({ projectId })}
              >
                {archiveProject.isPending ? "Archiving…" : "Archive project"}
              </button>
            )}
            {projectData.state === "active" ? (
              <a className="button button-primary" href="#source-media">
                Source video
              </a>
            ) : null}
          </div>
        </div>

        {isRenaming ? (
          <form className="rename-project-form" onSubmit={submitRename}>
            <label className="field-label" htmlFor="rename-project-title">
              Project title
            </label>
            <div className="inline-field">
              <input
                className="text-input"
                id="rename-project-title"
                maxLength={200}
                required
                value={draftTitle}
                onChange={(event) => setDraftTitle(event.target.value)}
              />
              <button
                className="button button-primary"
                type="submit"
                disabled={
                  renameProject.isPending || draftTitle.trim().length === 0
                }
              >
                {renameProject.isPending ? "Saving…" : "Save title"}
              </button>
            </div>
          </form>
        ) : null}

        {mutationError === undefined ? null : (
          <p className="form-error workspace-error" role="alert">
            {mutationError}
          </p>
        )}

        <ul className="analysis-chips" aria-label="Dashboard modules">
          {moduleNames.map((name) => (
            <li key={name}>{name}</li>
          ))}
        </ul>

        <section className="dashboard-grid" aria-label="Analysis dashboard">
          <SourceMediaPanel
            projectId={projectId}
            projectState={projectData.state}
          />
          {modulePlaceholders.map(([name, description, moduleId]) => (
            <AnalysisCard
              description={description}
              job={analysisJobs.find(
                (candidate) => candidate.module_id === moduleId,
              )}
              key={name}
              name={name}
              cancelPendingJobId={
                cancelAnalysis.isPending
                  ? cancelAnalysis.variables?.jobId
                  : undefined
              }
              onCancel={(jobId) => cancelAnalysis.mutate({ projectId, jobId })}
            />
          ))}
          <article className="analysis-card notes-card">
            <div className="analysis-card-heading">
              <h2>Notes</h2>
              <span className="status-pill status-pill-human">
                Journalist authored
              </span>
            </div>
            <p>
              Your project notes will be saved separately from machine-produced
              results.
            </p>
          </article>
        </section>
      </main>
    </div>
  );
}

function AnalysisCard({
  name,
  description,
  job,
  cancelPendingJobId,
  onCancel,
}: {
  name: string;
  description: string;
  job: AnalysisJobResponse | undefined;
  cancelPendingJobId: string | undefined;
  onCancel: (jobId: string) => void;
}) {
  const latestAttempt = job?.attempts.at(-1);
  const progress =
    latestAttempt?.progress_completed !== null &&
    latestAttempt?.progress_completed !== undefined &&
    latestAttempt.progress_total !== null
      ? (latestAttempt.progress_completed / latestAttempt.progress_total) * 100
      : undefined;
  const status =
    job === undefined
      ? "Waiting for analysis"
      : job.state === "running" && job.cancel_requested_at !== null
        ? "Canceling"
        : jobStateLabel(job.state);
  const errorMessage = job?.public_failure_message;
  const isCancelable =
    job !== undefined &&
    ["waiting_for_dependencies", "ready", "running", "retry_wait"].includes(
      job.state,
    ) &&
    job.cancel_requested_at === null;

  return (
    <article className="analysis-card">
      <div className="analysis-card-heading">
        <h2>{name}</h2>
        <span
          className={`status-pill ${
            job?.state === "succeeded"
              ? "status-pill-ready"
              : job?.state === "failed" || job?.state === "blocked"
                ? "status-pill-error"
                : ""
          }`}
        >
          {status}
        </span>
      </div>
      <p>{errorMessage ?? latestAttempt?.progress_message ?? description}</p>
      {job?.state === "running" ? (
        <div className="analysis-progress">
          <span>{latestAttempt?.progress_stage ?? "Working"}</span>
          <progress
            aria-label={`${name} progress`}
            max={100}
            value={progress}
          />
        </div>
      ) : null}
      {isCancelable ? (
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

function jobStateLabel(state: string): string {
  const labels: Record<string, string> = {
    waiting_for_dependencies: "Waiting for dependencies",
    ready: "Queued",
    running: "Running",
    retry_wait: "Retry scheduled",
    succeeded: "Complete",
    failed: "Failed",
    blocked: "Blocked",
    canceled: "Canceled",
  };
  return labels[state] ?? state.replaceAll("_", " ");
}

function isTerminalJobState(state: string): boolean {
  return ["succeeded", "failed", "blocked", "canceled"].includes(state);
}

function LoadingScreen({ label }: { label: string }) {
  return (
    <div className="app-canvas">
      <AppHeader />
      <main className="loading-shell" aria-live="polite">
        <span className="loading-dot" aria-hidden="true" />
        {label}
      </main>
    </div>
  );
}
