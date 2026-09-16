import './globals.css';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: '免费智能选校评估 — Gobob SOHO',
  description: '3 分钟智能评估，为你匹配最适合的留学院校。由 Gobob SOHO 提供。',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="text-slate-800 antialiased">
        {/* R-Design 2026-09-16: 顶部品牌装饰条 — 一条暖橙渐变, 视觉锚点 */}
        <div className="h-1 bg-gradient-to-r from-primary-500 via-primary-400 to-primary-600" />

        <header className="bg-white/80 backdrop-blur-md border-b border-slate-200/70 sticky top-0 z-30 shadow-[0_1px_0_rgba(15,23,42,0.02)]">
          <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2.5 font-bold text-lg group">
              <span className="inline-flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-primary-600 text-white text-xl shadow-glow-primary group-hover:scale-105 transition-transform">
                🎓
              </span>
              <span className="tracking-tight">
                Gobob SOHO
                <span className="ml-2 text-xs font-medium text-primary-700 bg-primary-50 border border-primary-200 rounded-full px-2 py-0.5">
                  智能选校
                </span>
              </span>
            </Link>
            <nav className="flex items-center gap-5 text-sm">
              <Link href="/assessment" className="text-slate-600 hover:text-primary-600 font-medium transition-colors">
                智能评估
              </Link>
              <Link
                href="/assessment"
                className="inline-flex items-center gap-1.5 bg-gradient-to-br from-primary-500 to-primary-600 text-white font-semibold px-4 py-2 rounded-xl shadow-glow-primary hover:from-primary-600 hover:to-primary-700 hover:-translate-y-0.5 hover:shadow-lift transition-all"
              >
                免费评估
                <span aria-hidden>→</span>
              </Link>
            </nav>
          </div>
        </header>

        <main className="min-h-[calc(100vh-16rem)]">{children}</main>

        <footer className="border-t border-slate-200/70 mt-20 py-10 bg-white/50 backdrop-blur">
          <div className="max-w-6xl mx-auto px-4 text-center">
            <div className="flex items-center justify-center gap-2 text-slate-500 text-sm">
              <span className="inline-flex items-center justify-center w-6 h-6 rounded-lg bg-primary-100 text-primary-700 text-xs">🎓</span>
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
