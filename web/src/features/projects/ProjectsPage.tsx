import { useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useNavigate } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";

import { ApiError } from "../../api/fetcher";
import {
  getListProjectsApiProjectsGetQueryKey,
  useCreateProjectApiProjectsPost,
  useGetCurrentUserApiAuthMeGet,
  useListProjectsApiProjectsGet,
} from "../../api/generated/client";
import { AppHeader } from "../../components/AppHeader";

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

export function ProjectsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const currentUser = useGetCurrentUserApiAuthMeGet({
    query: { retry: false },
  });
  const projects = useListProjectsApiProjectsGet({
    query: { enabled: currentUser.isSuccess, retry: false },
  });
  const createProject = useCreateProjectApiProjectsPost({
    mutation: {
      onSuccess: async (response) => {
        if (response.status !== 201) return;
        await queryClient.invalidateQueries({
          queryKey: getListProjectsApiProjectsGetQueryKey(),
        });
        await navigate({
          to: "/projects/$projectId",
          params: { projectId: response.data.id },
        });
      },
    },
  });
  const sessionData =
    currentUser.data?.status === 200 ? currentUser.data.data : undefined;
  const projectList =
    projects.data?.status === 200 ? projects.data.data : undefined;

  if (
    currentUser.error instanceof ApiError &&
    currentUser.error.status === 401
  ) {
    return <Navigate to="/login" replace />;
  }

  if (projects.error instanceof ApiError && projects.error.status === 401) {
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

  if (currentUser.isPending) {
    return <LoadingProjects />;
  }

  function submitProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createProject.mutate({ data: { title } });
  }

  const createError =
    createProject.error instanceof ApiError
      ? createProject.error.message
      : createProject.isError
        ? "The project could not be created."
        : undefined;

  return (
    <div className="app-canvas">
      <AppHeader
        username={sessionData?.user.username}
        isAdmin={sessionData?.user.is_admin}
      />
      <main className="projects-shell">
        <div className="projects-heading">
          <div>
            <p className="eyebrow">Video forensics workspace</p>
            <h1>Projects</h1>
            <p className="intro-copy">
              Revisit an investigation or create a new saved workspace.
            </p>
          </div>
          <button
            className="button button-primary"
            type="button"
            onClick={() => setShowCreate((visible) => !visible)}
          >
            {showCreate ? "Cancel" : "+ New project"}
          </button>
        </div>

        {showCreate ? (
          <section
            className="create-project-card"
            aria-labelledby="create-project-title"
          >
            <div>
              <h2 id="create-project-title">Create a project</h2>
              <p>
                Give the investigation a clear working title. You can change it
                later.
              </p>
            </div>
            <form className="create-project-form" onSubmit={submitProject}>
              <label className="field-label" htmlFor="project-title">
                Project title
              </label>
              <div className="inline-field">
                <input
                  className="text-input"
                  id="project-title"
                  maxLength={200}
                  required
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
                <button
                  className="button button-primary"
                  type="submit"
                  disabled={
                    createProject.isPending || title.trim().length === 0
                  }
                >
                  {createProject.isPending ? "Creating…" : "Create"}
                </button>
              </div>
              {createError === undefined ? null : (
                <p className="form-error" role="alert">
                  {createError}
                </p>
              )}
            </form>
          </section>
        ) : null}

        {projects.isPending ? (
          <div className="project-state" aria-live="polite">
            Loading projects…
          </div>
        ) : projects.error instanceof ApiError ? (
          <section className="status-card">
            <h2>Projects could not be loaded</h2>
            <p>{projects.error.message}</p>
            <button
              className="button button-secondary"
              type="button"
              onClick={() => projects.refetch()}
            >
              Try again
            </button>
          </section>
        ) : projectList?.length === 0 ? (
          <section className="empty-projects">
            <span className="empty-projects-icon" aria-hidden="true">
              ＋
            </span>
            <h2>No projects yet</h2>
            <p>
              Create a saved workspace before uploading your first source video.
            </p>
            <button
              className="button button-primary"
              type="button"
              onClick={() => setShowCreate(true)}
            >
              Create your first project
            </button>
          </section>
        ) : (
          <section className="project-grid" aria-label="Saved projects">
            {projectList?.map((project) => (
              <Link
                className="project-card"
                key={project.id}
                to="/projects/$projectId"
                params={{ projectId: project.id }}
              >
                <div className="project-card-preview" aria-hidden="true">
                  <span>V</span>
                </div>
                <div className="project-card-body">
                  <div className="project-card-title-row">
                    <h2>{project.title}</h2>
                    <span className="status-pill">{project.state}</span>
                  </div>
                  <p>No source video uploaded</p>
                  <time dateTime={project.updated_at}>
                    Updated {dateFormatter.format(new Date(project.updated_at))}
                  </time>
                </div>
              </Link>
            ))}
          </section>
        )}
      </main>
    </div>
  );
}

function LoadingProjects() {
  return (
    <div className="app-canvas">
      <AppHeader />
      <main className="loading-shell" aria-live="polite">
        <span className="loading-dot" aria-hidden="true" />
        Loading projects…
      </main>
    </div>
  );
}
