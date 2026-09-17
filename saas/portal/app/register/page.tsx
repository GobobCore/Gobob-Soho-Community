'use client';

/**
 * 获客门户 · 机构自助注册页
 * 用户填表 → 创建新机构 + owner 账号 → 自动登录 → 跳 soho-app
 */
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Building2, User, Lock, ArrowRight, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Container } from '@/components/ui/Container';

const APP_URL = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:19003';

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    org_name: '',
    username: '',
    password: '',
    owner_name: '',
    contact_phone: '',
    contact_email: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function update(k: string, v: string) {
    setForm(f => ({ ...f, [k]: v }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    // 校验
    if (form.password.length < 8) { setError('密码至少 8 位'); return; }
    if (!/^[a-zA-Z0-9_.-]+$/.test(form.username)) { setError('用户名只能是英文字母、数字、_ . -'); return; }
    setLoading(true);
    try {
      const res = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        const msg = typeof d.detail === 'string' ? d.detail : (d.detail?.[0]?.msg || `注册失败 HTTP ${res.status}`);
        throw new Error(msg);
      }
      const data = await res.json();
      // 把 token + user 存 localStorage (soho-app 用同样 key)
      localStorage.setItem('soho_token', data.token);
      localStorage.setItem('soho_user', JSON.stringify(data.user));
      // 跳转到 soho-app 登录页(让它读取 token 后跳到 dashboard)
      window.location.href = APP_URL + '?token=' + encodeURIComponent(data.token);
    } catch (e) {
      setError(e instanceof Error ? e.message : '注册失败，请稍后再试');
    }
    setLoading(false);
  }

  return (
    <Container className="py-12 md:py-20" size="md">
      <div className="max-w-xl mx-auto">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-600 text-white mb-4 shadow-glow-primary">
            <Building2 className="w-7 h-7" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">创建你的留学工作室</h1>
          <p className="mt-3 text-slate-600">注册即开 14 天免费试用 · 无需信用卡</p>
        </div>

        <form onSubmit={submit} className="bg-white rounded-2xl border border-slate-200/70 shadow-lift p-6 md:p-8 space-y-5">
          {error && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-red-700 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              <Building2 className="w-4 h-4 inline-block mr-1.5 text-primary-600" />
              机构名称
            </label>
            <input
              required minLength={2} maxLength={100}
              value={form.org_name}
              onChange={e => update('org_name', e.target.value)}
              placeholder="例: 我的留学工作室"
              className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              <User className="w-4 h-4 inline-block mr-1.5 text-primary-600" />
              老板/主管姓名
            </label>
            <input
              required minLength={1} maxLength={50}
              value={form.owner_name}
              onChange={e => update('owner_name', e.target.value)}
              placeholder="您的姓名"
              className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">手机</label>
              <input
                value={form.contact_phone}
                onChange={e => update('contact_phone', e.target.value)}
                placeholder="13800000000"
                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">邮箱</label>
              <input
                type="email"
                value={form.contact_email}
                onChange={e => update('contact_email', e.target.value)}
                placeholder="you@example.com"
                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
            </div>
          </div>

          <hr className="border-slate-100" />

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">登录用户名</label>
            <input
              required minLength={3} maxLength={32}
              value={form.username}
              onChange={e => update('username', e.target.value)}
              placeholder="3-32 位英文字母/数字/_ . -"
              className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              <Lock className="w-4 h-4 inline-block mr-1.5 text-primary-600" />
              密码
            </label>
            <input
              required minLength={8}
              type="password"
              value={form.password}
              onChange={e => update('password', e.target.value)}
              placeholder="至少 8 位"
              className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-3 text-base disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '创建中…' : '创建账号并开始使用'}
            {!loading && <ArrowRight className="w-5 h-5" />}
          </button>

          <div className="text-xs text-slate-500 text-center pt-2 space-y-1">
            <div className="inline-flex items-center gap-1.5 text-emerald-600">
              <CheckCircle2 className="w-3.5 h-3.5" />
              1-2 个协作账号免费，3 个及以上 ¥1000/账号/年
            </div>
            <div>注册即表示同意 <Link href="#" className="text-primary-600 hover:underline">服务条款</Link> 和 <Link href="/privacy" className="text-primary-600 hover:underline">隐私政策</Link></div>
            <div className="pt-2">已有账号？<Link href="/assessment" className="text-primary-600 hover:underline font-medium">先去评估 →</Link></div>
          </div>
        </form>
      </div>
    </Container>
  );
}
