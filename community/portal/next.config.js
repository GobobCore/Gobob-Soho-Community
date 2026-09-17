/** @type {import('next').NextConfig} */
// R-Refactor 2026-09-17 16:30: 社区版 portal 物理隔离 — 默认反代到 19011 社区 backend
// 社区版 portal 与社区版 app 共用同一 backend, 获客数据走 /api/leads 写入社区版线索池
const BACKEND = process.env.SOHO_BACKEND_URL || 'http://127.0.0.1:19011';

const nextConfig = {
  async rewrites() {
    return [
      // 社区版 portal 数据请求 → 社区 backend (19011)
      // 留资走 /api/leads → 社区版线索池 (跟社区版 app 数据关联)
      { source: '/api/assessment/:path*', destination: `${BACKEND}/api/assessment/:path*` },
      { source: '/api/leads/:path*', destination: `${BACKEND}/api/leads/:path*` },
      // 社区版无自助注册 (单机构自托管, 由机构手动建账号)
      // 社区版无 SaaS 收银台 (开源版按次付费场景不在社区版 self-host 范围)
    ];
  },
};

module.exports = nextConfig;