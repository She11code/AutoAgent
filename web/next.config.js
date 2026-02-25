/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 开发时允许访问本地后端 API
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
