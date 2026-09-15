/**
 * ConfidenceBadge - T12 (2026-07-18) 置信度展示组件
 *
 * 显示评估结果的置信度等级 + 样本量 + 95% 置信区间。
 *
 * 用法:
 *   <ConfidenceBadge
 *     label="high"
 *     sampleSize={21}
 *     ciLow={65}
 *     ciHigh={85}
 *     source="alumni_outcomes"
 *   />
 *
 * 4 档语义:
 *   - high:   🟢 高置信度 (≥8 样本 或 跨学位补充)
 *   - medium: 🟡 中等 (4-7 样本 或 少量 + 跨学位)
 *   - low:    🟠 低 (1-3 样本 + 无补充)
 *   - none:   ⚪ 暂无数据 (走算法兜底)
 */
'use client';

import { CheckCircle2, AlertCircle, AlertTriangle, HelpCircle } from 'lucide-react';
import clsx from 'clsx';

export type ConfidenceLabel = 'high' | 'medium' | 'low' | 'none';

export interface ConfidenceBadgeProps {
  label: ConfidenceLabel;
  sampleSize?: number;
  ciLow?: number;
  ciHigh?: number;
  source?: 'alumni_outcomes' | 'peer_schools' | 'algorithm';
  showSample?: boolean;       // 是否显示 "N=21"
  showCI?: boolean;           // 是否显示 "[65%–85%]"
  size?: 'sm' | 'md';
}

const labelConfig: Record<ConfidenceLabel, {
  text: string;
  shortText: string;
  bgClass: string;
  textClass: string;
  icon: typeof CheckCircle2;
  tooltip: string;
}> = {
  high: {
    text: '高置信度',
    shortText: '高',
    bgClass: 'bg-success-50 border-success-200',
    textClass: 'text-success-700',
    icon: CheckCircle2,
    tooltip: '基于 8+ 真实案例 / 同校数据充足，结果可靠',
  },
  medium: {
    text: '中等置信',
    shortText: '中',
    bgClass: 'bg-amber-50 border-amber-200',
    textClass: 'text-amber-700',
    icon: AlertTriangle,
    tooltip: '样本 4-7 个 / 部分跨学位补充，结果有一定参考价值',
  },
  low: {
    text: '低置信度',
    shortText: '低',
    bgClass: 'bg-orange-50 border-orange-200',
    textClass: 'text-orange-700',
    icon: AlertCircle,
    tooltip: '样本极少，结果仅供参考',
  },
  none: {
    text: '算法估算',
    shortText: '估',
    bgClass: 'bg-gray-50 border-gray-200',
    textClass: 'text-gray-600',
    icon: HelpCircle,
    tooltip: '暂无校友数据，使用算法预测',
  },
};

const sourceLabels = {
  alumni_outcomes: '真实案例',
  peer_schools: '同类学校',
  algorithm: '算法',
};

export function ConfidenceBadge({
  label,
  sampleSize,
  ciLow,
  ciHigh,
  source,
  showSample = true,
  showCI = false,
  size = 'sm',
}: ConfidenceBadgeProps) {
  const cfg = labelConfig[label];
  const Icon = cfg.icon;
  const sizeClasses = size === 'sm'
    ? 'px-1.5 py-0.5 text-[10px] gap-1'
    : 'px-2 py-1 text-xs gap-1.5';

  const tooltipParts = [cfg.tooltip];
  if (showSample && sampleSize !== undefined && sampleSize > 0) {
    tooltipParts.push(`样本: ${sampleSize} 个真实案例`);
  }
  if (source && source !== 'algorithm') {
    tooltipParts.push(`来源: ${sourceLabels[source]}`);
  } else if (source === 'algorithm') {
    tooltipParts.push('来源: 算法估算（无校友数据）');
  }
  if (showCI && ciLow !== undefined && ciHigh !== undefined) {
    tooltipParts.push(`95% 置信区间: ${ciLow.toFixed(0)}% – ${ciHigh.toFixed(0)}%`);
  }
  const tooltip = tooltipParts.join('\n');

  return (
    <span
      className={clsx(
        'inline-flex items-center font-medium rounded-full border',
        cfg.bgClass,
        cfg.textClass,
        sizeClasses,
      )}
      title={tooltip}
    >
      <Icon className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} />
      <span>{cfg.shortText}</span>
      {showSample && sampleSize !== undefined && sampleSize > 0 && (
        <span className="font-mono opacity-75">
          · N={sampleSize}
        </span>
      )}
      {showCI && ciLow !== undefined && ciHigh !== undefined && (
        <span className="font-mono opacity-75 ml-0.5">
          [{ciLow.toFixed(0)}–{ciHigh.toFixed(0)}%]
        </span>
      )}
    </span>
  );
}