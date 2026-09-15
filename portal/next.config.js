/** @type {import('next').NextConfig} */
const BACKEND = process.env.SOHO_BACKEND_URL || 'http://127.0.0.1:19001';

const nextConfig = {
  async rewrites() {
    return [
      // 获客门户的所有数据请求 → SOHO backend（/api/assessment/* 代理 + /api/leads/capture）
      { source: '/api/assessment/:path*', destination: `${BACKEND}/api/assessment/:path*` },
      { source: '/api/leads/:path*', destination: `${BACKEND}/api/leads/:path*` },
    ];
  },
};

module.exports = nextConfig;
