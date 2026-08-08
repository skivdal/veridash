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

import type { AdminUserResponse } from "../../api/generated/schemas";
import { createAppRouter } from "../../router";

beforeEach(() => {
  vi.stubGlobal("scrollTo", vi.fn());
  // biome-ignore lint/suspicious/noDocumentCookie: jsdom does not implement Cookie Store API.
  document.cookie = "veridash_csrf=test-csrf-token; path=/";
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  // biome-ignore lint/suspicious/noDocumentCookie: jsdom does not implement Cookie Store API.
  document.cookie = "veridash_csrf=; max-age=0; path=/";
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderAdminUsers() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createAppRouter(
    createMemoryHistory({ initialEntries: ["/admin/users"] }),
  );
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("user administration", () => {
  it("creates a user and requires confirmation before deactivation", async () => {
    const users: AdminUserResponse[] = [
      {
        id: 1,
        username: "administrator",
        email: "administrator@example.test",
        is_admin: true,
        is_enabled: true,
        last_login_at: "2026-08-08T20:00:00Z",
        project_count: 3,
        created_at: "2026-08-01T12:00:00Z",
      },
      {
        id: 2,
        username: "journalist",
        email: "journalist@example.test",
        is_admin: false,
        is_enabled: true,
        last_login_at: null,
        project_count: 1,
        created_at: "2026-08-02T12:00:00Z",
      },
    ];
    const requests: Array<{ url: string; method: string; body?: string }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        requests.push({ url, method, body: init?.body?.toString() });
        if (url === "/api/auth/me") {
          return jsonResponse({
            user: {
              id: 1,
              username: "administrator",
              email: "administrator@example.test",
              is_admin: true,
            },
          });
        }
        if (url === "/api/admin/users" && method === "GET") {
          return jsonResponse(users);
        }
        if (url === "/api/admin/users" && method === "POST") {
          const body = JSON.parse(String(init?.body)) as {
            username: string;
            email: string;
          };
          const created: AdminUserResponse = {
            id: 3,
            username: body.username,
            email: body.email,
            is_admin: false,
            is_enabled: true,
            last_login_at: null,
            project_count: 0,
            created_at: "2026-08-08T20:10:00Z",
          };
          users.push(created);
          return jsonResponse(created, 201);
        }
        if (url === "/api/admin/users/2/deactivate" && method === "POST") {
          const targetIndex = users.findIndex((user) => user.id === 2);
          const target = users[targetIndex];
          if (target === undefined) throw new Error("test user is missing");
          const deactivated = { ...target, is_enabled: false };
          users[targetIndex] = deactivated;
          return jsonResponse(deactivated);
        }
        return jsonResponse({}, 404);
      }),
    );

    renderAdminUsers();

    expect(await screen.findByRole("heading", { name: "Users" })).toBeDefined();
    expect(await screen.findByText("journalist@example.test")).toBeDefined();
    expect(screen.getByText("Never")).toBeDefined();

    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "new-journalist" },
    });
    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "new-journalist@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Initial password"), {
      target: { value: "a sufficiently long password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create user" }));

    expect(
      await screen.findByText("new-journalist@example.test"),
    ).toBeDefined();
    expect(
      requests.some(
        (request) =>
          request.url === "/api/admin/users" && request.method === "POST",
      ),
    ).toBe(true);

    fireEvent.click(
      screen.getByRole("button", { name: "Deactivate journalist" }),
    );
    expect(
      screen.getByRole("button", {
        name: "Confirm deactivation of journalist",
      }),
    ).toBeDefined();
    expect(
      requests.some((request) => request.url.endsWith("/deactivate")),
    ).toBe(false);
    fireEvent.click(
      screen.getByRole("button", {
        name: "Confirm deactivation of journalist",
      }),
    );

    await waitFor(() => {
      expect(
        requests.some(
          (request) =>
            request.url === "/api/admin/users/2/deactivate" &&
            request.method === "POST",
        ),
      ).toBe(true);
    });
    expect(await screen.findByText("Inactive")).toBeDefined();
  });
});
