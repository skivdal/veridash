import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";

import { useLogoutApiAuthLogoutPost } from "../api/generated/client";

interface AppHeaderProps {
  username?: string;
}

export function AppHeader({ username }: AppHeaderProps) {
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
          V
        </span>
        <span>VeriDash</span>
      </Link>

      {username === undefined ? null : (
        <div className="account-actions">
          <span className="username">{username}</span>
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
