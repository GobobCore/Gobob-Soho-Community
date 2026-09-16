import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: '免费智能选校评估 — Gobob SOHO',
  description: '3 分钟智能评估，为你匹配最适合的留学院校。由 Gobob SOHO 提供。',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="text-slate-800 antialiased">
        {/* R-Design 2026-09-16 v2: 落地页去掉 header 导航 (用户反馈单页不需要), 只保留顶部品牌装饰条 */}
        <div className="h-1 bg-gradient-to-r from-primary-500 via-primary-400 to-primary-600" />

        <main className="min-h-[calc(100vh-12rem)]">{children}</main>

        <footer className="border-t border-slate-200/70 mt-20 py-10 bg-white/50 backdrop-blur">
          <div className="max-w-6xl mx-auto px-4 text-center">
            <div className="flex items-center justify-center gap-2 text-slate-500 text-sm">
              <span>
                由 <span className="font-semibold text-primary-700">Gobob SOHO</span> 提供 · 开源留学机构管理系统
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-400">
              院校数据由 Gobob Data API 提供 · 你的数据完全私有
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
