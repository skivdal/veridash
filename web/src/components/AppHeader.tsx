import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";

import { useLogoutApiAuthLogoutPost } from "../api/generated/client";

interface AppHeaderProps {
  username?: string;
  isAdmin?: boolean;
}

export function AppHeader({ username, isAdmin = false }: AppHeaderProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const logout = useLogoutApiAuthLogoutPost({
    mutation: {
      onSuccess: async () => {
        queryClient.clear();
        await navigate({ to: "/login" });
      },
    },
  });

  return (
    <header className="app-header">
      <Link className="brand" to="/projects" aria-label="VeriDash projects">
        <span className="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 44 44">
            <title>VeriDash mark</title>
            <path d="M31.5 7.5A16 16 0 1 0 35 30" />
            <path d="m12.5 19.5 7 11 15-18" />
            <path d="m31.5 31.5 7 9" />
          </svg>
        </span>
        <span className="brand-copy">
          <strong>VeriDash</strong>
          <small>Verification command center</small>
        </span>
      </Link>

      {username === undefined ? null : (
        <div className="account-actions">
          {isAdmin ? (
            <Link className="button button-quiet" to="/admin/users">
              Users
            </Link>
          ) : null}
          <span className="username">{username}</span>
          <Link className="button button-quiet" to="/account/password">
            Change password
          </Link>
          <button
            className="button button-quiet"
            type="button"
            disabled={logout.isPending}
            onClick={() => logout.mutate()}
          >
            {logout.isPending ? "Signing out…" : "Sign out"}
          </button>
        </div>
      )}
    </header>
  );
}
