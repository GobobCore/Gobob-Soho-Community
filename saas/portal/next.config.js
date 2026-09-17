/** @type {import('next').NextConfig} */
// R-Refactor 2026-09-17 16:30: SaaS portal 物理隔离 — 默认反代到 19001 SaaS backend
const BACKEND = process.env.SOHO_BACKEND_URL || 'http://127.0.0.1:19001';

const nextConfig = {
  async rewrites() {
    return [
      // 获客门户的所有数据请求 → SaaS backend (19001)
      { source: '/api/assessment/:path*', destination: `${BACKEND}/api/assessment/:path*` },
      { source: '/api/leads/:path*', destination: `${BACKEND}/api/leads/:path*` },
      // 注册 (SaaS 多机构) + 开源版按次购买 (SaaS 收银台)
      { source: '/api/register', destination: `${BACKEND}/api/register` },
      { source: '/api/saas/:path*', destination: `${BACKEND}/api/saas/:path*` },
    ];
  },
};

module.exports = nextConfig;
