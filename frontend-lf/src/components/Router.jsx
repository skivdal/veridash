import { useState, useEffect } from "react";

export function Router({ routes }) {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const RouteComponent = routes[path] || routes["*"];
  return RouteComponent ? <RouteComponent /> : null;
}

