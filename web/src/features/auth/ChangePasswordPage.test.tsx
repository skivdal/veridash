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
  // biome-ignore lint/suspicious/noDocumentCookie: jsdom does not implement Cookie Store API.
  document.cookie = "veridash_csrf=test-csrf-token; path=/";
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  // biome-ignore lint/suspicious/noDocumentCookie: jsdom does not implement Cookie Store API.
  document.cookie = "veridash_csrf=; max-age=0; path=/";
});

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderChangePassword() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createAppRouter(
    createMemoryHistory({ initialEntries: ["/account/password"] }),
  );
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

function fillPasswords(
  current: string,
  password: string,
  confirmation = password,
) {
  fireEvent.change(screen.getByLabelText("Current password"), {
    target: { value: current },
  });
  fireEvent.change(screen.getByLabelText("New password"), {
    target: { value: password },
  });
  fireEvent.change(screen.getByLabelText("Confirm new password"), {
    target: { value: confirmation },
  });
}

const session = {
  user: {
    id: 1,
    username: "journalist",
    email: "user@example.test",
    is_admin: false,
  },
};

describe("password changes", () => {
  it("validates confirmation, shows server errors, and clears passwords after success", async () => {
    const requests: RequestInit[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/api/auth/me") return jsonResponse(session);
        if (
          String(input) === "/api/auth/change-password" &&
          init !== undefined
        ) {
          requests.push(init);
          if (requests.length === 1) {
            return jsonResponse(
              {
                status: 400,
                code: "incorrect_current_password",
                detail: "The current password is incorrect.",
              },
              400,
            );
          }
          return new Response(null, { status: 204 });
        }
        return jsonResponse({}, 404);
      }),
    );

    renderChangePassword();
    await screen.findByLabelText("Current password");
    expect(
      screen
        .getByRole("link", { name: "Change password" })
        .getAttribute("href"),
    ).toBe("/account/password");
    fillPasswords(
      "wrong password",
      "a new long password",
      "a different password",
    );
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "The new passwords do not match.",
    );
    expect(requests).toHaveLength(0);

    fillPasswords("wrong password", "a new long password");
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "The current password is incorrect.",
    );

    fillPasswords("the correct password", "a new long password");
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));
    expect((await screen.findByRole("status")).textContent).toBe(
      "Your password has been changed.",
    );
    expect(requests).toHaveLength(2);
    expect(JSON.parse(String(requests[1]?.body))).toEqual({
      current_password: "the correct password",
      new_password: "a new long password",
      confirm_password: "a new long password",
    });
    expect(new Headers(requests[1]?.headers).get("X-CSRF-Token")).toBe(
      "test-csrf-token",
    );
    for (const label of [
      "Current password",
      "New password",
      "Confirm new password",
    ]) {
      expect((screen.getByLabelText(label) as HTMLInputElement).value).toBe("");
    }
  });

  it("prevents duplicate submissions and allows retry after a network failure", async () => {
    let rejectChange: ((reason: Error) => void) | undefined;
    const changeRequest = vi.fn(
      () =>
        new Promise<Response>((_resolve, reject) => {
          rejectChange = reject;
        }),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input) === "/api/auth/me") return jsonResponse(session);
        return changeRequest();
      }),
    );
    renderChangePassword();
    await screen.findByLabelText("Current password");
    fillPasswords("the correct password", "a new long password");
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));
    const pending = await screen.findByRole("button", {
      name: "Changing password…",
    });
    expect((pending as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(pending);
    expect(changeRequest).toHaveBeenCalledTimes(1);
    rejectChange?.(new TypeError("Failed to fetch"));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Please try again.",
    );
    expect(
      (
        screen.getByRole("button", {
          name: "Change password",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
  });

  it.each(["initial", "submit"])(
    "redirects to sign in when the %s session has expired",
    async (expiry) => {
      let expired = expiry === "initial";
      vi.stubGlobal(
        "fetch",
        vi.fn(async (input: RequestInfo | URL) => {
          if (String(input) === "/api/auth/me" && !expired)
            return jsonResponse(session);
          expired = true;
          return jsonResponse(
            {
              status: 401,
              code: "authentication_required",
              detail: "Sign in to continue.",
            },
            401,
          );
        }),
      );
      const router = renderChangePassword();
      if (expiry === "submit") {
        await screen.findByLabelText("Current password");
        fillPasswords("the correct password", "a new long password");
        fireEvent.click(
          screen.getByRole("button", { name: "Change password" }),
        );
      }
      await waitFor(() =>
        expect(router.state.location.pathname).toBe("/login"),
      );
      expect(screen.queryByLabelText("Current password")).toBeNull();
    },
  );
});
