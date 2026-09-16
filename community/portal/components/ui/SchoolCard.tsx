/**
 * SchoolCard - T-Fix (2026-07-18) 学校大块卡片
 *
 * 显示: logo + 学校名(中/英) + 国旗 + 匹配分 + 置信徽章 + tier 标签
 * 视觉: 每块更大 (3 列 instead of 5), 更易点击
 *
 * R-Feature (2026-07-21): 支持 onClick 弹窗模式 — 传 onClick 时拦截点击,
 *   不跳转; 否则维持原 Link 跳转行为。
 */
'use client';

import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { SchoolLogo, countryFlag } from './SchoolLogo';
import { ConfidenceBadge, type ConfidenceLabel } from '@/components/assessment/ConfidenceBadge';

interface SchoolCardProps {
  school_id: string;
  name: string;
  name_cn?: string;
  country?: string;
  logo_url?: string | null;
  website?: string | null;
  match_score?: number;
  admission_probability_value?: number;
  confidence_label?: 'high' | 'medium' | 'low' | 'none';
  alumni_sample_size?: number;
  calibration_source?: 'alumni_outcomes' | 'peer_schools' | 'algorithm';
  tier: 'reach' | 'match' | 'safety';
  rank_qs?: number | null;
  // T-Fix (2026-07-18): 用于 deep-link 预填 (从评估页跳过来时)
  user_profile?: {
    gpa?: number;
    school_tier?: string;
    toefl_score?: number;
    gre_score?: number;
    ielts_score?: number;
    target_degree?: string;
    target_major?: string;
    target_country?: string;
    research_exp?: number;
    internship_exp?: number;
    publications?: number;
  };
  // R-Feature (2026-07-21): 弹窗点击回调 - 父组件控制弹窗状态 (空则跳页面)
  onClick?: (schoolId: string, name?: string) => void;
}

const TIER_LABEL: Record<string, string> = {
  reach: '可冲',
  match: '可稳',
  safety: '可保',
};
const TIER_COLOR: Record<string, string> = {
  reach: 'bg-orange-50 text-orange-700 border-orange-200',
  match: 'bg-primary-50 text-primary-700 border-primary-200',
  safety: 'bg-green-50 text-green-700 border-green-200',
};

const baseClass = 'block bg-white hover:bg-primary-50/30 px-3 py-3 rounded-xl border border-gray-200 hover:border-primary-300 hover:shadow-md transition-all group';

export function SchoolCard(props: SchoolCardProps) {
  const displayName = props.name_cn || props.name;
  const englishName = props.name_cn && props.name_cn !== props.name ? props.name : null;
  const prob = props.admission_probability_value;
  const flag = countryFlag(props.country);

  // T-Fix (2026-07-18): 跳转带 user profile 参数 (避免单校页要重新填表)
  const params = new URLSearchParams();
  if (props.user_profile) {
    const p = props.user_profile;
    if (p.gpa != null) params.set('gpa', String(p.gpa));
    if (p.school_tier) params.set('tier', p.school_tier);
    if (p.toefl_score != null) params.set('toefl', String(p.toefl_score));
    if (p.gre_score != null) params.set('gre', String(p.gre_score));
    if (p.ielts_score != null) params.set('ielts', String(p.ielts_score));
    if (p.target_degree) params.set('degree', p.target_degree);
    if (p.target_major) params.set('major', p.target_major);
    if (p.target_country) params.set('country', p.target_country);
    if (p.research_exp != null) params.set('research', String(p.research_exp));
    if (p.internship_exp != null) params.set('internship', String(p.internship_exp));
    if (p.publications != null) params.set('publications', String(p.publications));
  }
  const href = `/schools/${props.school_id}/match${params.toString() ? '?' + params.toString() : ''}`;

  const body = (
    <>
      {/* 第一行: logo + 名字 + tier 标签 */}
      <div className="flex items-start gap-3 mb-2">
        <SchoolLogo
          logoUrl={props.logo_url}
          schoolName={props.name}
          schoolNameCn={props.name_cn}
          schoolId={props.school_id}
          size="md"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-base" title={props.country}>{flag}</span>
            {props.rank_qs && (
              <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded font-mono">
                #{props.rank_qs}
              </span>
            )}
            <span className={`text-[10px] px-1.5 py-0.5 rounded border ${TIER_COLOR[props.tier]}`}>
              {TIER_LABEL[props.tier]}
            </span>
          </div>
          <div className="font-bold text-gray-800 text-sm line-clamp-1 mt-0.5" title={displayName}>
            {displayName}
          </div>
          {englishName && (
            <div className="text-[11px] text-gray-500 line-clamp-1" title={englishName}>
              {englishName}
            </div>
          )}
        </div>
      </div>

      {/* 第二行: 分数 + 置信度 */}
      <div className="flex items-center justify-between gap-2 mb-1">
        {prob !== undefined && prob !== null && (
          <div className="inline-flex items-baseline gap-1">
            <span className="text-lg font-bold text-purple-700">{prob.toFixed(0)}</span>
            <span className="text-[10px] text-gray-500">% 录取率</span>
          </div>
        )}
        {props.match_score !== undefined && (
          <span className="text-[10px] text-gray-500 font-mono">
            评分 {props.match_score.toFixed(0)}
          </span>
        )}
      </div>

      {/* 第三行: 置信度徽章 */}
      {props.confidence_label && (
        <div className="mt-2 flex items-center justify-between">
          <ConfidenceBadge
            label={props.confidence_label as ConfidenceLabel}
            sampleSize={props.alumni_sample_size}
            source={props.calibration_source}
            showSample
            showCI={false}
          />
          <ArrowRight className="w-3.5 h-3.5 text-gray-400 group-hover:text-primary-600 group-hover:translate-x-0.5 transition-all" />
        </div>
      )}
    </>
  );

  // R-Feature (2026-07-21): 有 onClick 走弹窗, 否则走 Link 跳转
  if (props.onClick) {
    return (
      <button
        type="button"
        onClick={() => props.onClick!(props.school_id, displayName)}
        className={`${baseClass} w-full text-left cursor-pointer`}
      >
        {body}
      </button>
    );
  }
  return (
    <Link href={href} className={baseClass}>
      {body}
    </Link>
  );
}