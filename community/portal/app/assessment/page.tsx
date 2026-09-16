'use client';

/**
 * 获客门户 · 智能评估页
 * 匿名填表 → 调 SOHO backend /api/assessment/match（转发 Gobob）→ 分层结果 → 留资钩子
 *
 * R-Design 2026-09-16 v2: emoji → lucide 扁平化单色图标
 */
import { useState } from 'react';
import { Sparkles, Lock, Target, Gift, Check, ArrowRight, AlertTriangle } from 'lucide-react';
import { Container } from '@/components/ui/Container';
import { Card } from '@/components/ui/Card';
import { SchoolCard } from '@/components/ui/SchoolCard';
import { MultiStageForm, type MultiStageFormData } from '@/components/assessment/MultiStageForm';
import LeadCapture from '@/components/LeadCapture';

type Match = {
  school_id: string;
  school_name?: string;
  school_name_cn?: string;
  name_cn?: string;
  name_en?: string;
  country?: string;
  logo_url?: string | null;
  admission_prob?: number;
  admission_probability_value?: number;
  rank_qs?: number | null;
  tier?: 'reach' | 'match' | 'safety';
};

type Result = {
  soho_assessment_id?: string;
  matches_by_tier?: { reach?: Match[]; match?: Match[]; safety?: Match[] };
  tier_groups?: { reach: Match[]; match: Match[]; safety: Match[] };
  tier_summary?: { reach_count: number; match_count: number; safety_count: number; recommendation?: { advice?: string } };
  total?: number;
  countries_analyzed?: string[];
};

function normalize(raw: any): Result {
  const r: Result = raw || {};
  if (!r.matches_by_tier && r.tier_groups) r.matches_by_tier = r.tier_groups;
  return r;
}

const TIER_META = [
  { key: 'reach' as const, label: '冲刺', color: 'text-orange-600', desc: '录取有挑战，但值得一试' },
  { key: 'match' as const, label: '匹配', color: 'text-blue-600', desc: '实力相当，录取概率高' },
  { key: 'safety' as const, label: '保底', color: 'text-emerald-600', desc: '稳妥选择，大概率录取' },
];

export default function AssessmentPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const [showCapture, setShowCapture] = useState(false);
  const [captured, setCaptured] = useState(false);
  const [pendingSchool, setPendingSchool] = useState<string>('');

  async function handleSubmit(form: MultiStageFormData) {
    setLoading(true); setError(''); setResult(null);
    try {
      const res = await fetch('/api/assessment/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ form }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || `评估失败 HTTP ${res.status}`);
      }
      const data = await res.json();
      setResult(normalize(data));
      // 结果出来后，滚到结果区并弹留资钩子（延迟一点让用户先看结果）
      setTimeout(() => { if (!captured) setShowCapture(true); }, 1200);
    } catch (e) {
      setError(e instanceof Error ? e.message : '评估失败，请稍后再试');
    }
    setLoading(false);
  }

  function onSchoolClick(schoolId: string, name?: string) {
    // 点击学校 → 引导留资（机构获客钩子）
    setPendingSchool(name || schoolId);
    if (!captured) setShowCapture(true);
  }

  const tier = result?.matches_by_tier;
  const hasResult = tier && (tier.reach?.length || tier.match?.length || tier.safety?.length);

  return (
    <Container className="py-10 md:py-14">
      {/* 头部 — 渐变文字 + 副标题 + 隐私说明 */}
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 bg-primary-50 border border-primary-200 text-primary-700 rounded-full px-4 py-1.5 text-xs font-semibold mb-4">
          <Sparkles className="w-3.5 h-3.5" />
          免费 · 30 秒 · 无需注册
        </div>
        <h1 className="text-3xl md:text-5xl font-bold tracking-tight">
          <span className="bg-gradient-to-r from-primary-600 via-primary-500 to-primary-700 bg-clip-text text-transparent">
            智能选校评估
          </span>
        </h1>
        <p className="mt-4 text-base md:text-lg text-slate-600 max-w-xl mx-auto">
          填写你的背景，匹配冲刺 / 稳妥 / 保底院校
        </p>
        <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-slate-400">
          <Lock className="w-3 h-3" />
          你的信息只用于生成匹配结果，不会被分享
        </p>
      </div>

      <Card className="shadow-lift">
        <MultiStageForm onSubmit={handleSubmit} loading={loading} />
      </Card>

      {error && (
        <div className="mt-6 mx-auto max-w-md bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex items-center justify-center gap-2 text-red-700 text-sm">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {hasResult && (
        <div className="mt-16 animate-fade-in-up">
          <div className="text-center mb-8">
            <div className="inline-flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-full px-4 py-1.5 text-xs font-semibold mb-4">
              <Target className="w-3.5 h-3.5" />
              为你找到 {(tier?.reach?.length || 0) + (tier?.match?.length || 0) + (tier?.safety?.length || 0)} 所匹配院校
            </div>
            <h2 className="text-3xl font-bold tracking-tight">你的匹配结果</h2>
            {result?.tier_summary?.recommendation?.advice && (
              <p className="mt-3 text-slate-600 max-w-2xl mx-auto">{result.tier_summary.recommendation.advice}</p>
            )}
          </div>

          {TIER_META.map((t) => {
            const list = (tier?.[t.key] || []) as Match[];
            if (!list.length) return null;
            return (
              <div key={t.key} className="mb-10">
                <div className="flex items-baseline gap-3 mb-4">
                  <h3 className={`text-xl font-bold ${t.color} flex items-center gap-2`}>
                    <span className={`inline-block w-1.5 h-6 rounded-full ${
                      t.key === 'reach' ? 'bg-orange-500' : t.key === 'match' ? 'bg-blue-500' : 'bg-emerald-500'
                    }`} />
                    {t.label}
                    <span className="text-base font-semibold text-slate-500">（{list.length}）</span>
                  </h3>
                  <span className="text-sm text-slate-400">{t.desc}</span>
                </div>
                <div className="grid md:grid-cols-2 gap-4">
                  {list.map((m) => (
                    <SchoolCard
                      key={m.school_id}
                      school_id={m.school_id}
                      name={m.name_en || m.school_name || ''}
                      name_cn={m.school_name_cn || m.name_cn}
                      country={m.country}
                      logo_url={m.logo_url}
                      admission_probability_value={m.admission_prob ?? m.admission_probability_value}
                      rank_qs={m.rank_qs}
                      tier={t.key}
                      onClick={onSchoolClick}
                    />
                  ))}
                </div>
              </div>
            );
          })}

          {/* 底部留资 CTA — 暖橙渐变 + 装饰 */}
          {!captured && (
            <div className="relative overflow-hidden mt-12 bg-gradient-to-br from-primary-600 via-primary-500 to-primary-700 rounded-3xl p-10 md:p-12 text-center text-white shadow-lift">
              <div aria-hidden className="absolute -top-20 -right-20 w-64 h-64 rounded-full bg-white/10 blur-2xl" />
              <div aria-hidden className="absolute -bottom-24 -left-24 w-72 h-72 rounded-full bg-primary-300/30 blur-3xl" />
              <div className="relative">
                <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-white/20 backdrop-blur mb-4">
                  <Gift className="w-7 h-7" />
                </div>
                <h3 className="text-2xl md:text-3xl font-bold tracking-tight">想要完整申请方案？</h3>
                <p className="mt-3 text-primary-50 max-w-md mx-auto">
                  留下联系方式，顾问为你定制选校清单和申请时间线
                </p>
                <button
                  onClick={() => setShowCapture(true)}
                  className="mt-7 inline-flex items-center gap-2 bg-white text-primary-700 font-bold px-8 py-4 rounded-2xl text-base shadow-lift hover:-translate-y-1 hover:shadow-[0_16px_40px_rgba(0,0,0,0.2)] transition-all"
                >
                  免费获取完整方案
                  <ArrowRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 留资弹窗 */}
      {showCapture && !captured && (
        <LeadCapture
          assessmentId={result?.soho_assessment_id}
          context={pendingSchool ? `对 ${pendingSchool} 感兴趣` : undefined}
          onClose={() => setShowCapture(false)}
          onDone={() => { setCaptured(true); setShowCapture(false); }}
        />
      )}

      {captured && (
        <div className="mt-10 bg-emerald-50 border-2 border-emerald-200 rounded-2xl p-8 text-center shadow-soft">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-emerald-500 text-white mb-3">
            <Check className="w-7 h-7" strokeWidth={2.5} />
          </div>
          <p className="text-emerald-800 font-semibold text-lg">已收到你的信息</p>
          <p className="text-emerald-600 text-sm mt-1">顾问会尽快联系你</p>
        </div>
      )}
    </Container>
  );
}
