/** @type {import('next').NextConfig} */
const nextConfig = {
  // output: "export",
  // only working in dev:
  async headers() {
    return [
      {
        source: "/",
        headers: [
          { key: "Access-Control-Allow-Credentials", value: "true" },
          { key: "Access-Control-Allow-Origin", value: "*" },
          { key: "Access-Control-Allow-Methods", value: "GET,DELETE,PATCH,POST,PUT,OPTIONS" },
          { key: "Access-Control-Allow-Headers", value: "*" },
        ]
      }
    ]
  },
  typescript: {
    "ignoreBuildErrors": true,
  }
};

export default nextConfig;
