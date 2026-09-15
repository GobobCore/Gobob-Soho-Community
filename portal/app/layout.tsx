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
      <body className="bg-slate-50 text-slate-800 antialiased">
        <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
          <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2 font-bold text-lg">
              <span className="text-2xl">🎓</span>
              <span>Gobob SOHO <span className="text-sm font-normal text-slate-400">智能选校</span></span>
            </Link>
            <nav className="flex items-center gap-6 text-sm">
              <Link href="/assessment" className="text-slate-600 hover:text-blue-600">智能评估</Link>
              <Link href="/assessment" className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
                免费评估
              </Link>
            </nav>
          </div>
        </header>
        <main>{children}</main>
        <footer className="border-t border-slate-200 mt-16 py-8 text-center text-sm text-slate-400">
          <p>由 Gobob SOHO 提供 · 开源留学机构管理系统</p>
        </footer>
      </body>
    </html>
  );
}
