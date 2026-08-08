import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiError } from "../../api/fetcher";
import {
  getGetProjectNoteApiProjectsProjectIdNoteGetQueryKey,
  useGetProjectNoteApiProjectsProjectIdNoteGet,
  useSaveProjectNoteApiProjectsProjectIdNotePut,
} from "../../api/generated/client";

export function NotesCard({
  projectId,
  readOnly,
}: {
  projectId: string;
  readOnly: boolean;
}) {
  const queryClient = useQueryClient();
  const note = useGetProjectNoteApiProjectsProjectIdNoteGet(projectId, {
    query: { retry: false },
  });
  const [draft, setDraft] = useState("");
  const [savedBody, setSavedBody] = useState<string | undefined>();
  const [revision, setRevision] = useState<number | undefined>();
  const save = useSaveProjectNoteApiProjectsProjectIdNotePut({
    mutation: {
      onSuccess: (response) => {
        if (response.status !== 200) return;
        queryClient.setQueryData(
          getGetProjectNoteApiProjectsProjectIdNoteGetQueryKey(projectId),
          response,
        );
        setSavedBody(response.data.body);
        setRevision(response.data.revision);
      },
    },
  });
  const response = note.data?.status === 200 ? note.data.data : undefined;

  useEffect(() => {
    if (response === undefined) return;
    if (revision === undefined) {
      setDraft(response.body);
      setSavedBody(response.body);
      setRevision(response.revision);
      return;
    }
    if (draft === savedBody && response.revision !== revision) {
      setDraft(response.body);
      setSavedBody(response.body);
      setRevision(response.revision);
    }
  }, [draft, response, revision, savedBody]);

  useEffect(() => {
    if (
      readOnly ||
      revision === undefined ||
      savedBody === undefined ||
      draft === savedBody ||
      save.isPending ||
      save.isError
    )
      return;
    const timeout = window.setTimeout(() => {
      save.mutate({
        projectId,
        data: { body: draft, expected_revision: revision },
      });
    }, 750);
    return () => window.clearTimeout(timeout);
  }, [draft, projectId, readOnly, revision, save, savedBody]);

  const error =
    save.error instanceof ApiError
      ? save.error.status === 409
        ? "These notes changed elsewhere. Copy any unsaved text, then reload the saved version."
        : save.error.message
      : note.error instanceof ApiError
        ? note.error.message
        : undefined;
  const saveStatus = save.isPending
    ? "Saving…"
    : error !== undefined
      ? "Not saved"
      : draft === savedBody
        ? "Saved"
        : "Waiting to save…";

  return (
    <article className="analysis-card notes-card">
      <div className="analysis-card-heading">
        <div>
          <p className="card-eyebrow">Journalist authored</p>
          <h2>Notes</h2>
        </div>
        <span className="status-pill status-pill-human" aria-live="polite">
          {saveStatus}
        </span>
      </div>
      <label className="visually-hidden" htmlFor="project-notes">
        Project notes
      </label>
      <textarea
        id="project-notes"
        className="notes-editor"
        maxLength={100_000}
        placeholder="Record observations, questions, and verification steps…"
        value={draft}
        disabled={readOnly || note.isPending || revision === undefined}
        onChange={(event) => {
          save.reset();
          setDraft(event.target.value);
        }}
      />
      <div className="notes-footer">
        <small>{draft.length.toLocaleString()} / 100,000 characters</small>
        {error === undefined ? null : <span role="alert">{error}</span>}
        {save.error instanceof ApiError && save.error.status === 409 ? (
          <button
            className="button button-secondary"
            type="button"
            onClick={() => window.location.reload()}
          >
            Reload saved notes
          </button>
        ) : null}
      </div>
    </article>
  );
}
