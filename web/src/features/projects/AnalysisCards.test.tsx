import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AnalysisJobResponse } from "../../api/generated/schemas";
import { ActivityLogCard } from "./ActivityLogCard";
import { TranscriptCard } from "./TranscriptCard";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function renderWithQueryClient(component: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>{component}</QueryClientProvider>,
  );
}

const transcriptJob = {
  id: "transcript-job",
  project_id: "project-id",
  source_media_id: "media-id",
  module_id: "transcribe",
  implementation_version: "1.0.0",
  result_schema_version: 1,
  display_name: "Transcription",
  resource_class: "gpu",
  cacheable: false,
  implementation_fingerprints: {},
  state: "succeeded",
  parameters: {},
  max_attempts: 3,
  next_attempt_at: null,
  ready_at: "2026-08-08T12:00:00Z",
  started_at: "2026-08-08T12:00:01Z",
  finished_at: "2026-08-08T12:00:02Z",
  cancel_requested_at: null,
  failure_kind: null,
  public_failure_message: null,
  diagnostic_id: null,
  reused: false,
  created_at: "2026-08-08T12:00:00Z",
  updated_at: "2026-08-08T12:00:02Z",
  attempts: [],
} satisfies AnalysisJobResponse;

const translationJob = {
  ...transcriptJob,
  id: "translation-job",
  module_id: "translate_transcript",
  display_name: "English translation",
  resource_class: "translation",
} satisfies AnalysisJobResponse;

describe("analysis result cards", () => {
  it("renders the immutable timestamped transcript without interpreting it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/artifacts")) {
          return jsonResponse([
            {
              id: "artifact-id",
              output_name: "transcript",
              kind: "blob",
              sha256_hex: "a".repeat(64),
              size_bytes: 100,
              media_type: "application/json",
              json_payload: null,
              schema_id: "veridash.transcript",
              schema_version: 1,
              created_at: "2026-08-08T12:00:02Z",
            },
          ]);
        }
        if (url.endsWith("/content")) {
          return jsonResponse({
            detected_language: "no",
            detected_language_probability: 0.97,
            inference_device: "cpu",
            inference_compute_type: "int8",
            segments: [
              {
                ordinal: 1,
                start_seconds: 3,
                end_seconds: 5,
                text: "Dette er kildens tale.",
              },
              {
                ordinal: 2,
                start_seconds: 6,
                end_seconds: 8,
                text: "Andre segment.",
              },
              {
                ordinal: 3,
                start_seconds: 9,
                end_seconds: 11,
                text: "Tredje segment.",
              },
              {
                ordinal: 4,
                start_seconds: 12,
                end_seconds: 14,
                text: "Fjerde segment.",
              },
              {
                ordinal: 5,
                start_seconds: 15,
                end_seconds: 17,
                text: "Femte segment er synlig med en gang.",
              },
            ],
          });
        }
        return jsonResponse({});
      }),
    );

    renderWithQueryClient(
      <TranscriptCard
        projectId="project-id"
        job={transcriptJob}
        translationJob={undefined}
        cancelPendingJobId={undefined}
        onCancel={vi.fn()}
        retryPendingJobId={undefined}
        onRetry={vi.fn()}
      />,
    );

    expect(await screen.findByText("Dette er kildens tale.")).toBeDefined();
    expect(
      screen.getByText("Femte segment er synlig med en gang."),
    ).toBeDefined();
    expect(screen.getByText("0:03")).toBeDefined();
    expect(screen.queryByText(/Inspect all/)).toBeNull();
    expect(
      screen.getByText(/No summary or interpretation is generated/),
    ).toBeDefined();
  });

  it("switches between the independently stored original and English translation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("transcript-job") && url.endsWith("/artifacts")) {
          return jsonResponse([
            {
              id: "transcript-artifact",
              output_name: "transcript",
              kind: "blob",
              sha256_hex: "a".repeat(64),
              size_bytes: 100,
              media_type: "application/json",
              json_payload: null,
              schema_id: "veridash.transcript",
              schema_version: 1,
              created_at: "2026-08-08T12:00:02Z",
            },
          ]);
        }
        if (url.includes("translation-job") && url.endsWith("/artifacts")) {
          return jsonResponse([
            {
              id: "translation-artifact",
              output_name: "translation",
              kind: "blob",
              sha256_hex: "b".repeat(64),
              size_bytes: 100,
              media_type: "application/json",
              json_payload: null,
              schema_id: "veridash.transcript_translation",
              schema_version: 1,
              created_at: "2026-08-08T12:00:04Z",
            },
          ]);
        }
        if (url.includes("transcript-artifact") && url.endsWith("/content")) {
          return jsonResponse({
            detected_language: "no",
            detected_language_probability: 0.97,
            inference_device: "cuda",
            inference_compute_type: "float16",
            segments: [
              {
                ordinal: 1,
                start_seconds: 3,
                end_seconds: 5,
                text: "Dette er kildens tale.",
              },
            ],
          });
        }
        if (url.includes("translation-artifact") && url.endsWith("/content")) {
          return jsonResponse({
            source_language: "no",
            target_language: "en",
            status: "translated",
            segments: [
              {
                ordinal: 1,
                start_seconds: 3,
                end_seconds: 5,
                text: "This is the source speech.",
              },
            ],
          });
        }
        return jsonResponse({});
      }),
    );

    renderWithQueryClient(
      <TranscriptCard
        projectId="project-id"
        job={transcriptJob}
        translationJob={translationJob}
        cancelPendingJobId={undefined}
        onCancel={vi.fn()}
        retryPendingJobId={undefined}
        onRetry={vi.fn()}
      />,
    );

    expect(await screen.findByText("Dette er kildens tale.")).toBeDefined();
    const englishButton = await screen.findByRole("button", {
      name: "English",
    });
    fireEvent.click(englishButton);

    expect(await screen.findByText("This is the source speech.")).toBeDefined();
    expect(screen.queryByText("Dette er kildens tale.")).toBeNull();
    expect(englishButton.getAttribute("aria-pressed")).toBe("true");
    expect(
      screen.getByText(/No summary or interpretation is generated/),
    ).toBeDefined();
  });

  it("hides high-frequency progress events until explicitly requested", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse([
          {
            id: 2,
            project_id: "project-id",
            job_id: "transcript-job",
            attempt_id: "attempt-id",
            event_type: "job.progress",
            source: "worker",
            payload_version: 1,
            payload: {
              stage: "transcribing",
              completed: 5000,
              total: 10000,
              message: "Transcribed 3 segments",
            },
            created_at: "2026-08-08T12:00:02Z",
          },
          {
            id: 1,
            project_id: "project-id",
            job_id: "transcript-job",
            attempt_id: null,
            event_type: "job.created",
            source: "scheduler",
            payload_version: 1,
            payload: {
              module_id: "transcribe",
              state: "waiting_for_dependencies",
            },
            created_at: "2026-08-08T12:00:01Z",
          },
        ]),
      ),
    );

    renderWithQueryClient(
      <ActivityLogCard projectId="project-id" jobs={[transcriptJob]} />,
    );

    expect(await screen.findByText("Requested Transcription")).toBeDefined();
    expect(screen.queryByText(/Transcribed 3 segments/)).toBeNull();

    fireEvent.click(screen.getByLabelText("Show progress updates"));

    expect(
      (await screen.findAllByText(/Transcribed 3 segments/)).length,
    ).toBeGreaterThan(0);
  });
});
