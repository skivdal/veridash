"use client";

import { createAuthClient } from "better-auth/client";
import { jazzPluginClient } from "jazz-tools/better-auth/auth/client";

export const betterAuthClient = createAuthClient({
  baseURL: "http://localhost:9090",
  plugins: [
    jazzPluginClient(),
  ],
});
