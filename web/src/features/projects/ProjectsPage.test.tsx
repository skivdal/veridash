import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
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
});
