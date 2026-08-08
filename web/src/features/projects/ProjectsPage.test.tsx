import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "../../router";

beforeEach(() => {
  vi.stubGlobal("scrollTo", vi.fn());
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderAt(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createAppRouter(
    createMemoryHistory({ initialEntries: [path] }),
  );
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("projects routing", () => {
  it("sends an unauthenticated visitor to the login screen", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          {
            type: "urn:veridash:problem:authentication_required",
            title: "Authentication required",
            status: 401,
            detail: "Sign in to continue.",
            code: "authentication_required",
          },
          401,
        ),
      ),
    );

    renderAt("/projects");

    expect(
      await screen.findByRole("heading", { name: "Welcome back" }),
    ).toBeDefined();
    expect(screen.getByLabelText("Username")).toBeDefined();
  });

  it("shows durable projects returned by the API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/auth/me") {
          return jsonResponse({ user: { id: 1, username: "journalist" } });
        }
        if (url === "/api/projects") {
          return jsonResponse([
            {
              id: "d879dca1-4994-4412-bc67-31c7a5ab534b",
              title: "Harbor footage",
              state: "active",
              created_at: "2026-08-08T12:00:00Z",
              updated_at: "2026-08-08T12:30:00Z",
              archived_at: null,
            },
          ]);
        }
        return jsonResponse({}, 404);
      }),
    );

    renderAt("/projects");

    expect(
      await screen.findByRole("heading", { name: "Projects" }),
    ).toBeDefined();
    expect(
      await screen.findByRole("heading", { name: "Harbor footage" }),
    ).toBeDefined();
    expect(screen.getByText("journalist")).toBeDefined();
  });

  it("shows the source-video uploader for a project without media", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/auth/me") {
          return jsonResponse({ user: { id: 1, username: "journalist" } });
        }
        if (url === "/api/projects/project-id") {
          return jsonResponse({
            id: "project-id",
            title: "Source review",
            state: "active",
            created_at: "2026-08-08T12:00:00Z",
            updated_at: "2026-08-08T12:00:00Z",
            archived_at: null,
          });
        }
        if (url === "/api/projects/project-id/media") {
          return jsonResponse(
            {
              type: "urn:veridash:problem:media_not_found",
              title: "Source video not found",
              status: 404,
              detail: "The requested source video does not exist.",
              code: "media_not_found",
            },
            404,
          );
        }
        if (url === "/api/projects/project-id/analyses") {
          return jsonResponse([]);
        }
        return jsonResponse({}, 404);
      }),
    );

    renderAt("/projects/project-id");

    expect(
      await screen.findByRole("heading", { name: "Source review" }),
    ).toBeDefined();
    expect(
      await screen.findByRole("heading", { name: "Source video" }),
    ).toBeDefined();
    expect(screen.getByLabelText("Choose video")).toBeDefined();
  });

  it("shows timestamped immutable frames and opens the review surface", async () => {
    let retryRequested = false;
    let savedNoteBody: string | undefined;
    let stitchSelection: string[] | undefined;
    let savedHiddenModules: string[] | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/auth/me") {
          return jsonResponse({ user: { id: 1, username: "journalist" } });
        }
        if (url === "/api/preferences/dashboard") {
          if (init?.method === "PUT") {
            const request = JSON.parse(String(init.body)) as {
              module_order: string[];
              hidden_modules: string[];
              expected_revision: number;
            };
            savedHiddenModules = request.hidden_modules;
            return jsonResponse({
              user_id: 1,
              module_order: request.module_order,
              hidden_modules: request.hidden_modules,
              revision: request.expected_revision + 1,
              updated_at: "2026-08-08T12:00:05Z",
            });
          }
          return jsonResponse({
            user_id: 1,
            module_order: [
              "source",
              "frames",
              "transcription",
              "detection",
              "metadata",
              "map",
              "notes",
            ],
            hidden_modules: [],
            revision: 0,
            updated_at: "2026-08-08T12:00:00Z",
          });
        }
        if (url === "/api/projects/project-id") {
          return jsonResponse({
            id: "project-id",
            title: "Frame review",
            state: "active",
            created_at: "2026-08-08T12:00:00Z",
            updated_at: "2026-08-08T12:00:00Z",
            archived_at: null,
          });
        }
        if (url === "/api/projects/project-id/media") {
          return jsonResponse({
            id: "media-id",
            project_id: "project-id",
            upload_state: "uploaded",
            original_filename: "source.mp4",
            media_type: "video/mp4",
            size_bytes: 100,
            sha256_hex: "a".repeat(64),
            created_at: "2026-08-08T12:00:00Z",
            uploaded_at: "2026-08-08T12:00:01Z",
            failure_message: null,
          });
        }
        if (url === "/api/projects/project-id/analyses") {
          return jsonResponse([
            {
              id: "frames-job",
              project_id: "project-id",
              source_media_id: "media-id",
              module_id: "extract_keyframes",
              implementation_version: "1.0.0",
              result_schema_version: 1,
              display_name: "Frames",
              resource_class: "cpu",
              cacheable: false,
              implementation_fingerprints: {
                ffmpeg_binary: "deployment-unpinned",
              },
              state: "succeeded",
              parameters: {},
              max_attempts: 3,
              next_attempt_at: null,
              ready_at: "2026-08-08T12:00:01Z",
              started_at: "2026-08-08T12:00:01Z",
              finished_at: "2026-08-08T12:00:02Z",
              cancel_requested_at: null,
              failure_kind: null,
              public_failure_message: null,
              diagnostic_id: null,
              reused: false,
              created_at: "2026-08-08T12:00:01Z",
              updated_at: "2026-08-08T12:00:02Z",
              attempts: [],
            },
            {
              id: "metadata-job",
              project_id: "project-id",
              source_media_id: "media-id",
              module_id: "probe_media",
              implementation_version: "1.0.0",
              result_schema_version: 1,
              display_name: "Metadata",
              resource_class: "cpu",
              cacheable: false,
              implementation_fingerprints: {},
              state: "failed",
              parameters: {},
              max_attempts: 3,
              next_attempt_at: null,
              ready_at: "2026-08-08T12:00:01Z",
              started_at: "2026-08-08T12:00:01Z",
              finished_at: "2026-08-08T12:00:02Z",
              cancel_requested_at: null,
              failure_kind: "invalid_input",
              public_failure_message: "Metadata could not be read.",
              diagnostic_id: "diagnostic-id",
              reused: false,
              created_at: "2026-08-08T12:00:01Z",
              updated_at: "2026-08-08T12:00:02Z",
              attempts: [],
            },
            {
              id: "coordinates-job",
              project_id: "project-id",
              source_media_id: "media-id",
              module_id: "extract_coordinates",
              implementation_version: "1.0.0",
              result_schema_version: 1,
              display_name: "Map",
              resource_class: "cpu",
              cacheable: true,
              implementation_fingerprints: {
                coordinate_parser: "iso6709-decimal-v1",
              },
              state: "succeeded",
              parameters: {},
              max_attempts: 3,
              next_attempt_at: null,
              ready_at: "2026-08-08T12:00:02Z",
              started_at: "2026-08-08T12:00:02Z",
              finished_at: "2026-08-08T12:00:03Z",
              cancel_requested_at: null,
              failure_kind: null,
              public_failure_message: null,
              diagnostic_id: null,
              reused: false,
              created_at: "2026-08-08T12:00:01Z",
              updated_at: "2026-08-08T12:00:03Z",
              attempts: [],
            },
          ]);
        }
        if (
          url === "/api/projects/project-id/analyses/frame-stitches" &&
          init?.method === "POST"
        ) {
          const request = JSON.parse(String(init.body)) as {
            selected_output_names: string[];
          };
          stitchSelection = request.selected_output_names;
          return jsonResponse({ id: "stitch-job" }, 201);
        }
        if (url === "/api/projects/project-id/note") {
          if (init?.method === "PUT") {
            const request = JSON.parse(String(init.body)) as {
              body: string;
              expected_revision: number;
            };
            savedNoteBody = request.body;
            return jsonResponse({
              project_id: "project-id",
              body: request.body,
              revision: request.expected_revision + 1,
              updated_at: "2026-08-08T12:00:04Z",
            });
          }
          return jsonResponse({
            project_id: "project-id",
            body: "Initial verification note",
            revision: 1,
            updated_at: "2026-08-08T12:00:03Z",
          });
        }
        if (url === "/api/projects/project-id/analyses/metadata-job/retry") {
          retryRequested = true;
          return jsonResponse({});
        }
        if (url === "/api/projects/project-id/analyses/frames-job/artifacts") {
          const common = {
            sha256_hex: "b".repeat(64),
            size_bytes: 100,
            created_at: "2026-08-08T12:00:02Z",
            schema_version: 1,
          };
          return jsonResponse([
            {
              ...common,
              id: "frame-artifact",
              output_name: "frames_000001",
              kind: "blob",
              media_type: "image/jpeg",
              json_payload: null,
              schema_id: "veridash.keyframe.jpeg",
            },
            {
              ...common,
              id: "frame-artifact-2",
              output_name: "frames_000002",
              kind: "blob",
              media_type: "image/jpeg",
              json_payload: null,
              schema_id: "veridash.keyframe.jpeg",
            },
            {
              ...common,
              id: "index-artifact",
              output_name: "index",
              kind: "json",
              media_type: "application/json",
              json_payload: {
                frames: [
                  {
                    output_name: "frames_000001",
                    ordinal: 1,
                    timestamp_seconds: 2.5,
                  },
                  {
                    output_name: "frames_000002",
                    ordinal: 2,
                    timestamp_seconds: 3.5,
                  },
                ],
              },
              schema_id: "veridash.keyframes.index",
            },
          ]);
        }
        if (
          url === "/api/projects/project-id/analyses/coordinates-job/artifacts"
        ) {
          return jsonResponse([
            {
              id: "coordinate-artifact",
              output_name: "result",
              kind: "json",
              sha256_hex: "c".repeat(64),
              size_bytes: 100,
              media_type: "application/json",
              json_payload: {
                status: "found",
                latitude: 55.6058,
                longitude: 13.0007,
                altitude_meters: null,
                candidates: [],
              },
              schema_id: "veridash.coordinates.embedded",
              schema_version: 1,
              created_at: "2026-08-08T12:00:03Z",
            },
          ]);
        }
        return jsonResponse({}, 404);
      }),
    );

    renderAt("/projects/project-id");

    const frame = await screen.findByRole("img", {
      name: "Video frame at 00:00:02",
    });
    expect(frame.getAttribute("src")).toContain(
      "/artifacts/frame-artifact/content",
    );
    fireEvent.click(screen.getByRole("button", { name: "Review all frames" }));
    expect(screen.getByRole("dialog")).toBeDefined();
    expect(
      screen.getByRole("heading", { name: "Extracted frames" }),
    ).toBeDefined();
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Select frame 2 for stitching" }),
    );
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Select frame 1 for stitching" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Stitch selected frames" }),
    );
    await waitFor(() =>
      expect(stitchSelection).toEqual(["frames_000002", "frames_000001"]),
    );
    expect(
      screen.getByText(/cross-project cache reuse is disabled/i),
    ).toBeDefined();
    expect(screen.getByText("55.605800° N, 13.000700° E")).toBeDefined();
    expect(screen.queryByTitle(/OpenStreetMap/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Load map" }));
    expect(screen.getByTitle(/OpenStreetMap/)).toBeDefined();
    expect(
      screen
        .getByRole("link", { name: "Open Google Street View" })
        .getAttribute("href"),
    ).toContain("map_action=pano");
    const notes = screen.getByRole("textbox", { name: "Project notes" });
    expect((notes as HTMLTextAreaElement).value).toBe(
      "Initial verification note",
    );
    fireEvent.change(notes, {
      target: { value: "Saved journalist observation" },
    });
    await waitFor(
      () => expect(savedNoteBody).toBe("Saved journalist observation"),
      {
        timeout: 2_000,
      },
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry analysis" }));
    await waitFor(() => expect(retryRequested).toBe(true));
    fireEvent.click(
      screen.getByRole("button", { name: "Customize dashboard" }),
    );
    fireEvent.click(screen.getByRole("checkbox", { name: "Show Map" }));
    fireEvent.click(screen.getByRole("button", { name: "Save dashboard" }));
    await waitFor(() => expect(savedHiddenModules).toEqual(["map"]));
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Map" })).toBeNull(),
    );
  });
});
