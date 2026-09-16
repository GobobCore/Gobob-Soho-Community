import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: '智能选校评估 — Gobob SOHO',
  description: '填写背景，30 秒匹配冲刺 / 匹配 / 保底院校',
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
