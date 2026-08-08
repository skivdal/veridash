import { afterEach, describe, expect, it, vi } from "vitest";

import { type ApiError, apiFetch } from "./fetcher";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch", () => {
  it("sends same-origin credentials and the CSRF cookie on mutations", async () => {
    // biome-ignore lint/suspicious/noDocumentCookie: jsdom does not implement Cookie Store API.
    document.cookie = "veridash_csrf=test-csrf-token; path=/";
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, _options?: RequestInit) =>
        Promise.resolve(
          new Response(JSON.stringify({ id: "project-id" }), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          }),
        ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await apiFetch<{
      data: { id: string };
      status: 201;
      headers: Headers;
    }>("/api/projects", { method: "POST", body: "{}" });

    expect(response.data.id).toBe("project-id");
    const requestOptions = fetchMock.mock.calls[0]?.[1];
    expect(requestOptions?.credentials).toBe("same-origin");
    expect(new Headers(requestOptions?.headers).get("X-CSRF-Token")).toBe(
      "test-csrf-token",
    );
  });

  it("throws a typed safe problem for non-success responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              type: "urn:veridash:problem:project_not_found",
              title: "Project not found",
              status: 404,
              detail: "The requested project does not exist.",
              code: "project_not_found",
            }),
            { status: 404 },
          ),
        ),
      ),
    );

    const request = apiFetch("/api/projects/missing", { method: "GET" });

    await expect(request).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      message: "The requested project does not exist.",
    } satisfies Partial<ApiError>);
  });
});
