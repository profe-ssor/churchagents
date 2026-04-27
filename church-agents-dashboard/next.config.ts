import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for container image (see docs/azure-deployment.md)
  output: "standalone",
  async headers() {
    return [
      {
        source: "/security",
        headers: [
          {
            key: "Cache-Control",
            value: "private, no-store, no-cache, must-revalidate, max-age=0",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
