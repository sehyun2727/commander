/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@commander/event-schemas"],
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
