import { defineConfig } from "orval";

export default defineConfig({
  veridash: {
    input: "./openapi.json",
    output: {
      target: "./src/api/generated/client.ts",
      schemas: "./src/api/generated/schemas",
      client: "react-query",
      httpClient: "fetch",
      clean: true,
    },
  },
});
