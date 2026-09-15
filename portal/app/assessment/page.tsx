'use client';

/**
 * 获客门户 · 智能评估页
 * 匿名填表 → 调 SOHO backend /api/assessment/match（转发 Gobob）→ 分层结果 → 留资钩子
 */
import { useState } from 'react';
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
    <Container className="py-10">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold">智能选校评估</h1>
        <p className="mt-2 text-slate-500">填写你的背景，30 秒匹配冲刺 / 匹配 / 保底院校</p>
      </div>

      <Card>
        <MultiStageForm onSubmit={handleSubmit} loading={loading} />
      </Card>

      {error && <div className="mt-6 text-center text-red-500 text-sm">{error}</div>}

      {hasResult && (
        <div className="mt-12">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold">你的匹配结果</h2>
            {result?.tier_summary?.recommendation?.advice && (
              <p className="mt-2 text-slate-500">{result.tier_summary.recommendation.advice}</p>
            )}
          </div>

          {TIER_META.map((t) => {
            const list = (tier?.[t.key] || []) as Match[];
            if (!list.length) return null;
            return (
              <div key={t.key} className="mb-8">
                <div className="flex items-baseline gap-3 mb-3">
                  <h3 className={`text-lg font-bold ${t.color}`}>{t.label}（{list.length}）</h3>
                  <span className="text-sm text-slate-400">{t.desc}</span>
                </div>
                <div className="grid md:grid-cols-2 gap-3">
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

          {/* 底部留资 CTA */}
          {!captured && (
            <div className="mt-8 bg-gradient-to-r from-blue-600 to-blue-700 rounded-2xl p-8 text-center text-white">
              <h3 className="text-xl font-bold">想要完整申请方案？</h3>
              <p className="mt-2 text-blue-100">留下联系方式，顾问为你定制选校清单和申请时间线</p>
              <button onClick={() => setShowCapture(true)}
                      className="mt-4 bg-white text-blue-700 font-semibold px-6 py-3 rounded-xl hover:bg-blue-50">
                免费获取完整方案
              </button>
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
        <div className="mt-8 bg-emerald-50 border border-emerald-200 rounded-2xl p-6 text-center text-emerald-700">
          ✓ 已收到你的信息，顾问会尽快联系你
        </div>
      )}
    </Container>
  );
}
