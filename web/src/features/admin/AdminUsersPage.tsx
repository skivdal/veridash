import { useQueryClient } from "@tanstack/react-query";
import { Navigate } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";

import { ApiError } from "../../api/fetcher";
import {
  getGetUsersApiAdminUsersGetQueryKey,
  useGetCurrentUserApiAuthMeGet,
  useGetUsersApiAdminUsersGet,
  usePostDeactivateUserApiAdminUsersUserIdDeactivatePost,
  usePostUserApiAdminUsersPost,
} from "../../api/generated/client";
import type { AdminUserResponse } from "../../api/generated/schemas";
import { AppHeader } from "../../components/AppHeader";

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatDate(value: string | null): string {
  return value === null ? "Never" : dateFormatter.format(new Date(value));
}

export function AdminUsersPage() {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmingUserId, setConfirmingUserId] = useState<number>();
  const currentUser = useGetCurrentUserApiAuthMeGet({
    query: { retry: false },
  });
  const session =
    currentUser.data?.status === 200 ? currentUser.data.data : undefined;
  const users = useGetUsersApiAdminUsersGet({
    query: { enabled: session?.user.is_admin === true, retry: false },
  });
  const userList = users.data?.status === 200 ? users.data.data : undefined;
  const createUser = usePostUserApiAdminUsersPost({
    mutation: {
      onSuccess: async (response) => {
        if (response.status !== 201) return;
        setUsername("");
        setEmail("");
        setPassword("");
        await queryClient.invalidateQueries({
          queryKey: getGetUsersApiAdminUsersGetQueryKey(),
        });
      },
    },
  });
  const deactivateUser = usePostDeactivateUserApiAdminUsersUserIdDeactivatePost(
    {
      mutation: {
        onSuccess: async (response) => {
          if (response.status !== 200) return;
          setConfirmingUserId(undefined);
          await queryClient.invalidateQueries({
            queryKey: getGetUsersApiAdminUsersGetQueryKey(),
          });
        },
      },
    },
  );

  if (
    currentUser.error instanceof ApiError &&
    currentUser.error.status === 401
  ) {
    return <Navigate to="/login" replace />;
  }
  if (session !== undefined && !session.user.is_admin) {
    return <Navigate to="/projects" replace />;
  }

  function submitUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createUser.mutate({ data: { username, email, password } });
  }

  const createError =
    createUser.error instanceof ApiError
      ? createUser.error.message
      : createUser.isError
        ? "The user could not be created."
        : undefined;
  const deactivateError =
    deactivateUser.error instanceof ApiError
      ? deactivateUser.error.message
      : deactivateUser.isError
        ? "The user could not be deactivated."
        : undefined;

  return (
    <div className="app-canvas">
      <AppHeader
        username={session?.user.username}
        isAdmin={session?.user.is_admin}
      />
      <main className="admin-users-shell">
        <div className="admin-users-heading">
          <div>
            <p className="eyebrow">Administration</p>
            <h1>Users</h1>
            <p className="intro-copy">
              Create local accounts and review access to the investigation
              workspace.
            </p>
          </div>
          {userList === undefined ? null : (
            <div className="user-total">
              <strong>{userList.length}</strong>
              <span>{userList.length === 1 ? "user" : "users"}</span>
            </div>
          )}
        </div>

        {currentUser.isPending ? (
          <p className="project-state">Checking administrator access…</p>
        ) : currentUser.isError ? (
          <AdminError
            title="Unable to check your session"
            detail="The server could not confirm your sign-in state."
            retry={() => currentUser.refetch()}
          />
        ) : (
          <div className="admin-users-layout">
            <section
              className="create-user-card"
              aria-labelledby="create-user-title"
            >
              <h2 id="create-user-title">Create a user</h2>
              <p>
                Share the credentials securely. VeriDash does not send email or
                offer self-service password resets.
              </p>
              <form className="form-stack" onSubmit={submitUser}>
                <label className="field-label" htmlFor="new-username">
                  Username
                </label>
                <input
                  className="text-input"
                  id="new-username"
                  maxLength={128}
                  required
                  autoComplete="off"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                />
                <label className="field-label" htmlFor="new-email">
                  Email address
                </label>
                <input
                  className="text-input"
                  id="new-email"
                  maxLength={320}
                  required
                  type="email"
                  autoComplete="off"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
                <label className="field-label" htmlFor="new-password">
                  Initial password
                </label>
                <input
                  className="text-input"
                  id="new-password"
                  minLength={12}
                  maxLength={1024}
                  required
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <p className="field-hint">At least 12 characters.</p>
                <button
                  className="button button-primary button-wide"
                  type="submit"
                  disabled={createUser.isPending}
                >
                  {createUser.isPending ? "Creating…" : "Create user"}
                </button>
                {createError === undefined ? null : (
                  <p className="form-error" role="alert">
                    {createError}
                  </p>
                )}
              </form>
            </section>

            <section
              className="users-card"
              aria-labelledby="system-users-title"
            >
              <div className="users-card-heading">
                <div>
                  <h2 id="system-users-title">System users</h2>
                  <p>Project counts include active and archived projects.</p>
                </div>
                <button
                  className="button button-quiet"
                  type="button"
                  disabled={users.isFetching}
                  onClick={() => users.refetch()}
                >
                  {users.isFetching ? "Refreshing…" : "Refresh"}
                </button>
              </div>

              {users.isPending ? (
                <p className="project-state">Loading users…</p>
              ) : users.error instanceof ApiError ? (
                <AdminError
                  title="Users could not be loaded"
                  detail={users.error.message}
                  retry={() => users.refetch()}
                />
              ) : (
                <div className="users-table-wrap">
                  <table className="users-table">
                    <thead>
                      <tr>
                        <th scope="col">User</th>
                        <th scope="col">Last login</th>
                        <th scope="col">Projects</th>
                        <th scope="col">Status</th>
                        <th scope="col">
                          <span className="visually-hidden">Actions</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {userList?.map((user) => (
                        <UserRow
                          key={user.id}
                          user={user}
                          isConfirming={confirmingUserId === user.id}
                          isPending={
                            deactivateUser.isPending &&
                            confirmingUserId === user.id
                          }
                          onBeginDeactivate={() => setConfirmingUserId(user.id)}
                          onCancelDeactivate={() =>
                            setConfirmingUserId(undefined)
                          }
                          onConfirmDeactivate={() =>
                            deactivateUser.mutate({ userId: user.id })
                          }
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {deactivateError === undefined ? null : (
                <p className="form-error users-action-error" role="alert">
                  {deactivateError}
                </p>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

interface UserRowProps {
  user: AdminUserResponse;
  isConfirming: boolean;
  isPending: boolean;
  onBeginDeactivate: () => void;
  onCancelDeactivate: () => void;
  onConfirmDeactivate: () => void;
}

function UserRow({
  user,
  isConfirming,
  isPending,
  onBeginDeactivate,
  onCancelDeactivate,
  onConfirmDeactivate,
}: UserRowProps) {
  return (
    <tr>
      <td>
        <strong>{user.username}</strong>
        <span>{user.email}</span>
      </td>
      <td>{formatDate(user.last_login_at)}</td>
      <td>{user.project_count}</td>
      <td>
        <span
          className={`user-status ${user.is_enabled ? "user-status-active" : "user-status-inactive"}`}
        >
          {user.is_admin
            ? "Administrator"
            : user.is_enabled
              ? "Active"
              : "Inactive"}
        </span>
      </td>
      <td className="user-actions-cell">
        {user.is_admin || !user.is_enabled ? null : isConfirming ? (
          <div className="deactivate-confirmation">
            <button
              className="button button-danger"
              type="button"
              aria-label={`Confirm deactivation of ${user.username}`}
              disabled={isPending}
              onClick={onConfirmDeactivate}
            >
              {isPending ? "Deactivating…" : "Confirm"}
            </button>
            <button
              className="button button-quiet"
              type="button"
              disabled={isPending}
              onClick={onCancelDeactivate}
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            className="button button-quiet"
            type="button"
            aria-label={`Deactivate ${user.username}`}
            onClick={onBeginDeactivate}
          >
            Deactivate
          </button>
        )}
      </td>
    </tr>
  );
}

function AdminError({
  title,
  detail,
  retry,
}: {
  title: string;
  detail: string;
  retry: () => void;
}) {
  return (
    <div className="admin-inline-error">
      <h2>{title}</h2>
      <p>{detail}</p>
      <button className="button button-secondary" type="button" onClick={retry}>
        Try again
      </button>
    </div>
  );
}
