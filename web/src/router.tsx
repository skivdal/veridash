import {
  createRootRoute,
  createRoute,
  createRouter,
  Navigate,
  Outlet,
  type RouterHistory,
} from "@tanstack/react-router";

import { AdminUsersPage } from "./features/admin/AdminUsersPage";
import { ChangePasswordPage } from "./features/auth/ChangePasswordPage";
import { LoginPage } from "./features/auth/LoginPage";
import { ProjectPage } from "./features/projects/ProjectPage";
import { ProjectsPage } from "./features/projects/ProjectsPage";

function AppShell() {
  return <Outlet />;
}

const rootRoute = createRootRoute({ component: AppShell });
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => <Navigate to="/projects" replace />,
});
const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginPage,
});
const projectsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects",
  component: ProjectsPage,
});
const changePasswordRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/account/password",
  component: ChangePasswordPage,
});
const adminUsersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/users",
  component: AdminUsersPage,
});
const projectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId",
  component: ProjectRoute,
});

function ProjectRoute() {
  const { projectId } = projectRoute.useParams();
  return <ProjectPage projectId={projectId} />;
}

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  changePasswordRoute,
  projectsRoute,
  projectRoute,
  adminUsersRoute,
]);

export function createAppRouter(history?: RouterHistory) {
  return createRouter({ routeTree, history });
}

export const router = createAppRouter();

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
