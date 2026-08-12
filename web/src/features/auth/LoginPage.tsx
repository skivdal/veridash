import { useQueryClient } from "@tanstack/react-query";
import { Navigate, useNavigate } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";

import { ApiError } from "../../api/fetcher";
import {
  getGetCurrentUserApiAuthMeGetQueryKey,
  useGetCurrentUserApiAuthMeGet,
  useLoginApiAuthLoginPost,
} from "../../api/generated/client";
import { AppHeader } from "../../components/AppHeader";

export function LoginPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const currentUser = useGetCurrentUserApiAuthMeGet({
    query: { retry: false },
  });
  const login = useLoginApiAuthLoginPost({
    mutation: {
      onSuccess: async () => {
        await queryClient.invalidateQueries({
          queryKey: getGetCurrentUserApiAuthMeGetQueryKey(),
        });
        await navigate({ to: "/projects" });
      },
    },
  });

  if (currentUser.isSuccess) {
    return <Navigate to="/projects" replace />;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    login.mutate({ data: { username, password } });
  }

  const errorMessage =
    login.error instanceof ApiError
      ? login.error.message
      : login.isError
        ? "Sign in failed. Please try again."
        : undefined;

  return (
    <div className="app-canvas">
      <AppHeader />
      <main className="auth-shell">
        <section className="auth-card" aria-labelledby="login-title">
          <p className="eyebrow">Video forensics workspace</p>
          <h1 id="login-title">Welcome back</h1>
          <p className="intro-copy">
            Sign in to continue working with your saved investigations.
          </p>

          <form className="form-stack" onSubmit={submit}>
            <label className="field-label" htmlFor="username">
              Username
            </label>
            <input
              className="text-input"
              id="username"
              name="username"
              autoComplete="username"
              required
              maxLength={128}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />

            <label className="field-label" htmlFor="password">
              Password
            </label>
            <input
              className="text-input"
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />

            {errorMessage === undefined ? null : (
              <p className="form-error" role="alert">
                {errorMessage}
              </p>
            )}

            <button
              className="button button-primary button-wide"
              type="submit"
              disabled={login.isPending}
            >
              {login.isPending ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="legacy-login-notice">
            If you want to use old Veridash, go to{" "}
            <a href="https://old.veridash.fotoverifier.eu">
              old.veridash.fotoverifier.eu
            </a>
          </p>
        </section>
      </main>
    </div>
  );
}
