import type { NextConfig } from "next";

const ENGINE_URL = process.env.ENGINE_URL ?? "http://localhost:8800";

const nextConfig: NextConfig = {
  async rewrites() {
    // Same-origin proxy to the AURA engine: auth cookies + SSE work with
    // zero hand-written proxy code.
    return [{ source: "/api/engine/:path*", destination: `${ENGINE_URL}/:path*` }];
  },
};

export default nextConfig;
