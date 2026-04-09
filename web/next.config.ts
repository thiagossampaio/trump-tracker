import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "t3.gstatic.com",
      },
    ],
  },
};

export default nextConfig;
