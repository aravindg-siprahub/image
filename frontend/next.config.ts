import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Expose env var to client bundle (must start with NEXT_PUBLIC_)
  env: {
    NEXT_PUBLIC_API_URL: "https://image-production-56f5.up.railway.app/api/v1",
  },
  // Disable memory-heavy checks during Railway deploy
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  experimental: {
    memoryBasedWorkersCount: true,
  }
};

export default nextConfig;
