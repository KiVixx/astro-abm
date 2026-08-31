import type { NextConfig } from "next";

const internalApiOrigin = (
  process.env.ASTRO_ABM_INTERNAL_API_ORIGIN || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR || ".next",
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${internalApiOrigin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
