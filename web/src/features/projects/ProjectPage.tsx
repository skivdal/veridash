import { Link, Navigate } from "@tanstack/react-router";

import { ApiError } from "../../api/fetcher";
import {
  useGetCurrentUserApiAuthMeGet,
  useGetProjectApiProjectsProjectIdGet,
} from "../../api/generated/client";
import { AppHeader } from "../../components/AppHeader";

const modulePlaceholders = [
  ["Source", "Upload one source video to begin the automatic analysis."],
  ["Metadata", "Container, stream, and embedded metadata will appear here."],
  ["Frames", "Extracted frames and stitching controls will appear here."],
  [
    "Transcription",
    "Timestamped source-language transcription will appear here.",
  ],
  ["Object Detection", "Detected objects will remain linked to source frames."],
  ["Map", "Verified embedded coordinates can be inspected here."],
] as const;

interface ProjectPageProps {
  projectId: string;
}

export function ProjectPage({ projectId }: ProjectPageProps) {
  const currentUser = useGetCurrentUserApiAuthMeGet({
    query: { retry: false },
  });
  const project = useGetProjectApiProjectsProjectIdGet(projectId, {
    query: { enabled: currentUser.isSuccess, retry: false },
  });
  const sessionData =
    currentUser.data?.status === 200 ? currentUser.data.data : undefined;
  const projectData =
    project.data?.status === 200 ? project.data.data : undefined;

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
              Saved project · No source video yet
            </p>
          </div>
          <button className="button button-primary" type="button" disabled>
            Upload video
          </button>
        </div>

        <ul className="analysis-chips" aria-label="Dashboard modules">
          {modulePlaceholders.map(([name]) => (
            <li key={name}>{name}</li>
          ))}
        </ul>

        <section className="dashboard-grid" aria-label="Analysis dashboard">
          {modulePlaceholders.map(([name, description]) => (
            <article className="analysis-card" key={name}>
              <div className="analysis-card-heading">
                <h2>{name}</h2>
                <span className="status-pill">Waiting for video</span>
              </div>
              <p>{description}</p>
            </article>
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
