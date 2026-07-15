/** @type {import('next').NextConfig} */
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // proxy API calls to the FastAPI web-api so the browser hits same-origin
    return [{ source: "/api/:path*", destination: `${API}/:path*` }];
  },
};

module.exports = nextConfig;
