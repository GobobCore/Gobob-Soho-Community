'use client';

/**
 * 开源版按次购买页
 * 机构自助下单买 Gobob Data API 调用次数, 台账模式 (不接在线支付)
 */
import { useState } from 'react';
import Link from 'next/link';
import { KeyRound, CheckCircle2, AlertCircle, ShoppingCart, Copy, Mail, Phone } from 'lucide-react';
import { Container } from '@/components/ui/Container';

const PACKAGES = [
  { calls: 10, label: '10 次体验包', price: 10, desc: '适合试用' },
  { calls: 50, label: '50 次小包', price: 50, desc: '适合刚起步', recommended: false },
  { calls: 100, label: '100 次标准包', price: 100, desc: '最常用', recommended: true },
  { calls: 500, label: '500 次专业包', price: 500, desc: '高频使用' },
];

export default function BuyKeyPage() {
  const [step, setStep] = useState<'select' | 'form' | 'done'>('select');
  const [calls, setCalls] = useState(100);
  const [form, setForm] = useState({
    org_name: '',
    contact_name: '',
    contact_email: '',
    contact_phone: '',
    note: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [orderNo, setOrderNo] = useState('');
  const [copied, setCopied] = useState(false);

  function update(k: string, v: string) {
    setForm(f => ({ ...f, [k]: v }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/saas/buy-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, calls }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        const msg = typeof d.detail === 'string' ? d.detail : (d.detail?.[0]?.msg || `提交失败 HTTP ${res.status}`);
        throw new Error(msg);
      }
      const data = await res.json();
      setOrderNo(data.order_no);
      setStep('done');
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交失败，请稍后再试');
    }
    setLoading(false);
  }

  async function copyOrderNo() {
    await navigator.clipboard.writeText(orderNo);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Container className="py-12 md:py-20" size="md">
      <div className="max-w-2xl mx-auto">
        {/* 头部 */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-600 text-white mb-4 shadow-glow-primary">
            <KeyRound className="w-7 h-7" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">购买 Gobob Data API 次数</h1>
          <p className="mt-3 text-slate-600">开源版机构专用 · 按次计费 · ¥1/次</p>
        </div>

        {step === 'select' && (
          <div className="space-y-6">
            <div className="grid md:grid-cols-2 gap-4">
              {PACKAGES.map((p) => (
                <button
                  key={p.calls}
                  onClick={() => setCalls(p.calls)}
                  className={`relative p-6 rounded-2xl border-2 text-left transition-all ${
                    calls === p.calls
                      ? 'border-primary-500 bg-primary-50 shadow-glow-primary'
                      : 'border-slate-200 bg-white hover:border-primary-200'
                  }`}
                >
                  {p.recommended && (
                    <span className="absolute -top-3 left-4 bg-primary-600 text-white text-xs font-bold px-2.5 py-1 rounded-full">推荐</span>
                  )}
                  <div className="text-3xl font-bold text-primary-700">{p.calls}</div>
                  <div className="text-sm text-slate-500 mt-1">次调用</div>
                  <div className="text-lg font-semibold text-slate-800 mt-3">¥{p.price}</div>
                  <div className="text-xs text-slate-400 mt-1">{p.desc}</div>
                </button>
              ))}
            </div>
            <button onClick={() => setStep('form')} className="btn-primary w-full py-3.5 text-base">
              已选 {calls} 次 / ¥{calls} — 填写联系信息
            </button>
            <p className="text-center text-sm text-slate-500">
              <Link href="/" className="hover:underline">← 返回首页</Link>
            </p>
          </div>
        )}

        {step === 'form' && (
          <form onSubmit={submit} className="bg-white rounded-2xl border border-slate-200/70 shadow-lift p-6 md:p-8 space-y-5">
            {error && (
              <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-red-700 text-sm">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="bg-primary-50 border border-primary-200 rounded-xl p-4 flex items-center justify-between">
              <div>
                <div className="text-sm text-slate-600">已选套餐</div>
                <div className="text-2xl font-bold text-primary-700">{calls} 次</div>
              </div>
              <div className="text-right">
                <div className="text-sm text-slate-600">应付</div>
                <div className="text-2xl font-bold text-slate-900">¥{calls}</div>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">机构名称</label>
              <input required minLength={2} maxLength={100} value={form.org_name}
                onChange={e => update('org_name', e.target.value)}
                placeholder="例: 我的留学工作室"
                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">联系人姓名</label>
              <input required minLength={1} maxLength={50} value={form.contact_name}
                onChange={e => update('contact_name', e.target.value)}
                placeholder="您的姓名"
                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  <Mail className="w-4 h-4 inline-block mr-1 text-primary-600" />
                  联系邮箱
                </label>
                <input required type="email" value={form.contact_email}
                  onChange={e => update('contact_email', e.target.value)}
                  placeholder="收 API Key 用"
                  className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  <Phone className="w-4 h-4 inline-block mr-1 text-primary-600" />
                  联系电话 (可选)
                </label>
                <input value={form.contact_phone}
                  onChange={e => update('contact_phone', e.target.value)}
                  placeholder="13800000000"
                  className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">备注 (可选)</label>
              <textarea value={form.note} onChange={e => update('note', e.target.value)}
                rows={2} placeholder="其他想说明的 (例如: 想要测试一段时间再付款)"
                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-xs text-blue-700">
              <div className="font-semibold mb-1">付款流程</div>
              <ol className="space-y-1 list-decimal list-inside">
                <li>提交本表单, 获得订单号 (例: SOKEY20260916XXXX)</li>
                <li>转账时备注订单号, 我们确认到账后开通 API Key</li>
                <li>Key 会通过你填的邮箱发送给你</li>
              </ol>
            </div>

            <div className="flex gap-3">
              <button type="button" onClick={() => setStep('select')}
                className="px-5 py-3 border border-slate-200 rounded-xl text-slate-600 text-sm font-medium hover:bg-slate-50">
                返回选套餐
              </button>
              <button type="submit" disabled={loading}
                className="btn-primary flex-1 py-3 text-base disabled:opacity-50">
                {loading ? '提交中…' : '提交订单'}
                {!loading && <ShoppingCart className="w-5 h-5" />}
              </button>
            </div>
          </form>
        )}

        {step === 'done' && (
          <div className="bg-white rounded-2xl border border-emerald-200 shadow-lift p-8 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500 text-white mb-4">
              <CheckCircle2 className="w-9 h-9" strokeWidth={2.5} />
            </div>
            <h2 className="text-2xl font-bold text-emerald-800">订单已提交</h2>
            <p className="mt-2 text-slate-600">我们会尽快确认到账并通过邮箱发送 API Key</p>

            <div className="mt-6 bg-slate-50 border border-slate-200 rounded-xl p-5">
              <div className="text-xs text-slate-500 mb-1">订单号</div>
              <div className="flex items-center justify-center gap-2">
                <code className="text-lg font-mono font-bold text-slate-800">{orderNo}</code>
                <button onClick={copyOrderNo}
                  className="inline-flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700 font-medium">
                  <Copy className="w-3.5 h-3.5" />
                  {copied ? '已复制' : '复制'}
                </button>
              </div>
              <div className="mt-3 pt-3 border-t border-slate-200 grid grid-cols-2 gap-3 text-left">
                <div>
                  <div className="text-xs text-slate-500">购买次数</div>
                  <div className="font-bold">{calls} 次</div>
                </div>
                <div>
                  <div className="text-xs text-slate-500">应付金额</div>
                  <div className="font-bold text-primary-700">¥{calls}</div>
                </div>
              </div>
            </div>

            <div className="mt-6 bg-amber-50 border border-amber-200 rounded-xl p-5 text-left text-sm">
              <div className="font-semibold text-amber-800 mb-2">付款方式</div>
              <ul className="text-amber-700 space-y-1.5 text-sm">
                <li><strong>方式 1:</strong> 银行转账到 [待补: 收款账户]</li>
                <li><strong>方式 2:</strong> 支付宝扫码 [待补: 二维码图]</li>
                <li><strong>方式 3:</strong> 微信转账 [待补: 收款码]</li>
              </ul>
              <div className="mt-3 pt-3 border-t border-amber-200 text-amber-800">
                <strong>务必在备注里填订单号</strong> — 否则我们对不上账
              </div>
            </div>

            <div className="mt-6 text-sm text-slate-500">
              查订单状态: <Link href={`/buy-key/${orderNo}`} className="text-primary-600 hover:underline font-medium">{orderNo}</Link>
            </div>
          </div>
        )}
      </div>
    </Container>
  );
}
