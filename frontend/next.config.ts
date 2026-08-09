import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Expose env var to client bundle (must start with NEXT_PUBLIC_)
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1",
  },
};

export default nextConfig;
