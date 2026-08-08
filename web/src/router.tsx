import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from "@tanstack/react-router";

import { ProjectsPage } from "./features/projects/ProjectsPage";

function AppShell() {
  return <Outlet />;
}

const rootRoute = createRootRoute({ component: AppShell });
const projectsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: ProjectsPage,
});

const routeTree = rootRoute.addChildren([projectsRoute]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
