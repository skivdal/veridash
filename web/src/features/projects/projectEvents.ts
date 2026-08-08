import type { QueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import {
  getGetProjectApiProjectsProjectIdGetQueryKey,
  getGetProjectNoteApiProjectsProjectIdNoteGetQueryKey,
  getGetProjectSourceMediaApiProjectsProjectIdMediaGetQueryKey,
  getListProjectAnalysesApiProjectsProjectIdAnalysesGetQueryKey,
  getListProjectEventLogApiProjectsProjectIdEventLogGetQueryKey,
} from "../../api/generated/client";

interface ProjectEventEnvelope {
  event_type?: string;
}

type EventSourceFactory = (url: string) => EventSource;

export function connectProjectEvents(
  projectId: string,
  onEvent: (eventType: string | undefined) => void,
  createEventSource: EventSourceFactory = (url) => new EventSource(url),
): () => void {
  const source = createEventSource(
    `/api/projects/${encodeURIComponent(projectId)}/events`,
  );
  source.addEventListener("project-sync", () => onEvent(undefined));
  source.addEventListener("project-event", (event) => {
    try {
      const envelope = JSON.parse((event as MessageEvent<string>).data) as
        | ProjectEventEnvelope
        | undefined;
      onEvent(envelope?.event_type);
    } catch {
      onEvent(undefined);
    }
  });
  return () => source.close();
}

export function useProjectEvents(
  projectId: string,
  queryClient: QueryClient,
  enabled: boolean,
) {
  useEffect(() => {
    if (!enabled || typeof EventSource === "undefined") return;
    return connectProjectEvents(projectId, (eventType) => {
      void queryClient.invalidateQueries({
        queryKey:
          getListProjectEventLogApiProjectsProjectIdEventLogGetQueryKey(
            projectId,
          ),
      });
      if (eventType === undefined || eventType.startsWith("job.")) {
        void queryClient.invalidateQueries({
          queryKey:
            getListProjectAnalysesApiProjectsProjectIdAnalysesGetQueryKey(
              projectId,
            ),
        });
      }
      if (eventType === undefined || eventType.startsWith("media.")) {
        void queryClient.invalidateQueries({
          queryKey:
            getGetProjectSourceMediaApiProjectsProjectIdMediaGetQueryKey(
              projectId,
            ),
        });
      }
      if (eventType === undefined || eventType.startsWith("project.")) {
        void queryClient.invalidateQueries({
          queryKey: getGetProjectApiProjectsProjectIdGetQueryKey(projectId),
        });
      }
      if (eventType === undefined || eventType === "project.note_updated") {
        void queryClient.invalidateQueries({
          queryKey:
            getGetProjectNoteApiProjectsProjectIdNoteGetQueryKey(projectId),
        });
      }
    });
  }, [enabled, projectId, queryClient]);
}
