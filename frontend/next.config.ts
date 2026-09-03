import type { NextConfig } from "next";

const apiOrigin = process.env.DOHAMUSIC_API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  experimental: {
    // Backend accepts 25MiB voice files; keep 1MiB for multipart metadata.
    proxyClientMaxBodySize: "26mb",
  },
  async rewrites() {
    return [{ source: "/backend/:path*", destination: `${apiOrigin}/:path*` }];
  },
};

export default nextConfig;
