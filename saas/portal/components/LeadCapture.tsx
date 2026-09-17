'use client';

/**
 * 留资钩子组件 — 评估后引导留联系方式 → 写入 SOHO leads（source=assessment）
 *
 * R-Feat 2026-09-16: SaaS 多机构支持 — 从 URL ?org=slug 拿机构标识
 * 机构分享自己的专属链接 (portal.gobob.cn/?org=demo-studio) 后, 留资进对应机构
 */
import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';

export default function LeadCapture({
  assessmentId,
  context,
  onClose,
  onDone,
}: {
  assessmentId?: string;
  context?: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const searchParams = useSearchParams();
  const orgSlug = searchParams?.get('org') || '';
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [wechat, setWechat] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  async function submit() {
    if (!name.trim()) { setErr('请填写称呼'); return; }
    if (!phone.trim() && !wechat.trim()) { setErr('请至少留一个联系方式（手机或微信）'); return; }
    setLoading(true); setErr('');
    try {
      // R-Feat 2026-09-16: SaaS 多机构 — 带 org=slug 参数
      const url = orgSlug
        ? `/api/leads/capture?org=${encodeURIComponent(orgSlug)}`
        : '/api/leads/capture';
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_name: name.trim(),
          student_phone: phone.trim() || undefined,
          student_wechat: wechat.trim() || undefined,
          source_detail: context || '智能评估页留资',
          assessment_id: assessmentId,
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || '提交失败');
      }
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : '提交失败，请重试');
    }
    setLoading(false);
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl w-full max-w-sm p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-1">
          <h3 className="font-bold text-lg">免费获取完整方案</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl">✕</button>
        </div>
        {context && <p className="text-sm text-blue-600 mb-3">{context}</p>}
        <p className="text-sm text-slate-500 mb-4">留下联系方式，顾问会尽快联系你</p>
        <div className="space-y-3">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="怎么称呼你 *"
                 className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500" />
          <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="手机号"
                 className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500" />
          <input value={wechat} onChange={(e) => setWechat(e.target.value)} placeholder="微信号"
                 className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500" />
          {err && <div className="text-sm text-red-500">{err}</div>}
          <button onClick={submit} disabled={loading}
                  className="w-full bg-blue-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {loading ? '提交中…' : '提交，获取方案'}
          </button>
        </div>
      </div>
    </div>
  );
}
