/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    formats: ['image/avif', 'image/webp'],
  },
  // Dev-only tooling. The injected <nextjs-portal> dev-tools button overlays the
  // bottom tab bar on mobile viewports and intercepts pointer events, so E2E
  // clicks land on it instead of the app. It does not exist in a production
  // build, so disabling it makes `next dev` match what users actually get.
  devIndicators: false,
};

module.exports = nextConfig;
