/** @type {import('next').NextConfig} */
const BACKEND = process.env.SOHO_BACKEND_URL || 'http://127.0.0.1:19001';

const nextConfig = {
  async rewrites() {
    return [
      // 获客门户的所有数据请求 → SOHO backend
      { source: '/api/assessment/:path*', destination: `${BACKEND}/api/assessment/:path*` },
      { source: '/api/leads/:path*', destination: `${BACKEND}/api/leads/:path*` },
      // 注册 + 开源版购买 (R-Feat 2026-09-16)
      { source: '/api/register', destination: `${BACKEND}/api/register` },
      { source: '/api/saas/:path*', destination: `${BACKEND}/api/saas/:path*` },
    ];
  },
};

module.exports = nextConfig;
