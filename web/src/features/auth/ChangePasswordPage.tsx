import { useQueryClient } from "@tanstack/react-query";
import { Link, Navigate } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";

import { ApiError } from "../../api/fetcher";
import {
  useGetCurrentUserApiAuthMeGet,
  usePostChangePasswordApiAuthChangePasswordPost,
} from "../../api/generated/client";
import { AppHeader } from "../../components/AppHeader";

export function ChangePasswordPage() {
  const queryClient = useQueryClient();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [confirmationError, setConfirmationError] = useState<string>();
  const [saved, setSaved] = useState(false);
  const currentUser = useGetCurrentUserApiAuthMeGet({
    query: { retry: false },
  });
  const session =
    currentUser.data?.status === 200 ? currentUser.data.data : undefined;
  const changePassword = usePostChangePasswordApiAuthChangePasswordPost({
    mutation: {
      gcTime: 0,
      onError: (error) => {
        if (error instanceof ApiError && error.status === 401) {
          queryClient.clear();
        }
      },
      onSuccess: (response) => {
        if (response.status !== 204) return;
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
        setSaved(true);
        changePassword.reset();
      },
    },
  });

  if (
    (currentUser.error instanceof ApiError &&
      currentUser.error.status === 401) ||
    (changePassword.error instanceof ApiError &&
      changePassword.error.status === 401)
  ) {
    return <Navigate to="/login" replace />;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (changePassword.isPending) return;
    setSaved(false);
    changePassword.reset();
    if (newPassword !== confirmPassword) {
      setConfirmationError("The new passwords do not match.");
      return;
    }
    setConfirmationError(undefined);
    changePassword.mutate({
      data: {
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      },
    });
  }

  const errorMessage =
    confirmationError ??
    (changePassword.error instanceof ApiError
      ? changePassword.error.message
      : changePassword.isError
        ? "Your password could not be changed. Please try again."
        : undefined);

  return (
    <div className="app-canvas">
      <AppHeader
        username={session?.user.username}
        isAdmin={session?.user.is_admin}
      />
      <main className="auth-shell">
        <section className="auth-card" aria-labelledby="change-password-title">
          <p className="eyebrow">Your account</p>
          <h1 id="change-password-title">Change password</h1>
          {currentUser.isPending ? (
            <p className="project-state">Checking your session…</p>
          ) : currentUser.isError ? (
            <div role="alert">
              <p className="form-error">Unable to check your session.</p>
              <button
                className="button button-secondary"
                type="button"
                onClick={() => currentUser.refetch()}
              >
                Try again
              </button>
            </div>
          ) : session === undefined ? null : (
            <>
              <p className="intro-copy">
                Enter your current password and your new password twice. Other
                sessions will be signed out after the change.
              </p>
              <form
                className="form-stack"
                onSubmit={submit}
                onChange={() => {
                  setSaved(false);
                  setConfirmationError(undefined);
                  changePassword.reset();
                }}
              >
                <input
                  type="text"
                  name="username"
                  autoComplete="username"
                  value={session.user.username}
                  hidden
                  readOnly
                />
                <label className="field-label" htmlFor="current-password">
                  Current password
                </label>
                <input
                  className="text-input"
                  id="current-password"
                  name="current-password"
                  type="password"
                  autoComplete="current-password"
                  required
                  maxLength={1024}
                  disabled={changePassword.isPending}
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                />
                <label className="field-label" htmlFor="new-password">
                  New password
                </label>
                <input
                  className="text-input"
                  id="new-password"
                  name="new-password"
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={12}
                  maxLength={1024}
                  aria-describedby="password-policy"
                  disabled={changePassword.isPending}
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                />
                <p className="field-hint" id="password-policy">
                  At least 12 characters.
                </p>
                <label className="field-label" htmlFor="confirm-password">
                  Confirm new password
                </label>
                <input
                  className="text-input"
                  id="confirm-password"
                  name="confirm-password"
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={12}
                  maxLength={1024}
                  aria-invalid={confirmationError !== undefined}
                  aria-describedby={
                    errorMessage === undefined ? undefined : "password-error"
                  }
                  disabled={changePassword.isPending}
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                />
                {errorMessage === undefined ? null : (
                  <p className="form-error" id="password-error" role="alert">
                    {errorMessage}
                  </p>
                )}
                {saved ? (
                  <p role="status">Your password has been changed.</p>
                ) : null}
                <button
                  className="button button-primary button-wide"
                  type="submit"
                  disabled={changePassword.isPending}
                >
                  {changePassword.isPending
                    ? "Changing password…"
                    : "Change password"}
                </button>
                <Link className="button button-quiet" to="/projects">
                  Back to projects
                </Link>
              </form>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
