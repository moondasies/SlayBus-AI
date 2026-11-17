/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Optional: serve the agent through this app at /api (one URL for both).
  // Set AGENT_PROXY_URL=http://localhost:8000 and NEXT_PUBLIC_API_URL=/api.
  async rewrites() {
    const agent = process.env.AGENT_PROXY_URL;
    return agent ? [{ source: "/api/:path*", destination: `${agent.replace(/\/$/, "")}/:path*` }] : [];
  },
};

export default nextConfig;
