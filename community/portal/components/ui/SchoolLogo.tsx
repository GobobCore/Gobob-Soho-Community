/**
 * SchoolLogo - T-Fix (2026-07-18) 学校 logo 组件
 *
 * 显示优先级:
 * 1. logo_url (DB schools.logo_url)
 * 2. 首字母 fallback (color based on hash of school_id)
 */
'use client';

import { useState } from 'react';

const PALETTE = [
  'bg-blue-500',     'bg-indigo-500',   'bg-purple-500',
  'bg-pink-500',     'bg-rose-500',     'bg-red-500',
  'bg-orange-500',   'bg-amber-500',    'bg-yellow-500',
  'bg-lime-500',     'bg-green-500',    'bg-emerald-500',
  'bg-teal-500',     'bg-cyan-500',     'bg-sky-500',
];

function hashColor(s: string): string {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash) + s.charCodeAt(i);
    hash |= 0;
  }
  return PALETTE[Math.abs(hash) % PALETTE.length];
}

function getInitials(name: string, name_cn?: string): string {
  // 优先用中文名 (通常 2-4 字), 否则英文
  const src = (name_cn && name_cn.length <= 6) ? name_cn : name;
  if (!src) return '?';
  // 如果是中文, 取后 2 字 (例 "麻省理工学院" → "理工")
  if (/[\u4e00-\u9fa5]/.test(src)) {
    return src.length <= 3 ? src : src.slice(-2);
  }
  // 英文: 取首字母 (例 "Massachusetts Institute of Technology" → "MIT")
  // 取每个空格分隔单词的首字母
  const words = src.split(/\s+/).filter(w => /^[A-Za-z]/.test(w));
  if (words.length === 0) return src.slice(0, 2).toUpperCase();
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return words.slice(0, 3).map(w => w[0]).join('').toUpperCase();
}

interface SchoolLogoProps {
  logoUrl?: string | null;
  schoolName?: string;
  schoolNameCn?: string;
  shortName?: string; // 备用: 如果已计算好的缩写 (TopSchools 使用)
  schoolId?: string;
  size?: 'sm' | 'md' | 'lg' | number;  // 支持 pixel number (向后兼容)
  className?: string;
}

export function SchoolLogo({ logoUrl, schoolName, schoolNameCn, shortName, schoolId = '', size = 'md', className = '' }: SchoolLogoProps) {
  const [imgError, setImgError] = useState(false);
  const useImg = logoUrl && !imgError;

  // 支持 pixel number (向后兼容 TopSchools) 和 preset
  const sizeClass =
    typeof size === 'number'
      ? ''  // 用 style 替代
      : {
          sm: 'w-10 h-10 text-xs',
          md: 'w-14 h-14 text-sm',
          lg: 'w-20 h-20 text-lg',
        }[size];
  const sizeStyle = typeof size === 'number' ? { width: `${size}px`, height: `${size}px` } : undefined;

  const initials = shortName || getInitials(schoolName || '', schoolNameCn);
  const colorClass = hashColor(schoolId || schoolName || '');

  if (useImg) {
    // logo_url 可能是相对路径 (/logos/xxx.png) 或完整 URL
    const src = logoUrl.startsWith('http') ? logoUrl : logoUrl;
    return (
      <div
        className={`${sizeClass} rounded-lg overflow-hidden bg-gray-100 flex-shrink-0 ${className}`}
        style={sizeStyle}
      >
      <img
        src={src}
        alt={schoolNameCn || schoolName}
        className="w-full h-full object-contain bg-white"
        // R-Feat (2026-07-22 22:35 SEO+GEO): 加 lazy + 显式 width/height 防止 CLS
        loading="lazy"
        decoding="async"
        width={typeof size === 'number' ? size : size === 'lg' ? 80 : size === 'md' ? 56 : 40}
        height={typeof size === 'number' ? size : size === 'lg' ? 80 : size === 'md' ? 56 : 40}
        onError={() => setImgError(true)}
      />
      </div>
    );
  }

  // Fallback: 首字母 + 颜色
  const fontSize = typeof size === 'number' ? Math.max(10, Math.floor(size * 0.4)) : undefined;
  return (
    <div
      className={`${sizeClass} ${colorClass} rounded-lg flex items-center justify-center text-white font-bold flex-shrink-0 ${className}`}
      style={{ ...sizeStyle, fontSize: fontSize ? `${fontSize}px` : undefined }}
      title={schoolNameCn || schoolName}
    >
      {initials}
    </div>
  );
}

/**
 * 国旗 emoji 助手 (基于 country 字符串)
 * 国家名 → emoji 国旗
 */
const COUNTRY_FLAG: Record<string, string> = {
  // 英文
  'United States': '🇺🇸', 'USA': '🇺🇸', 'US': '🇺🇸', 'America': '🇺🇸',
  'United Kingdom': '🇬🇧', 'UK': '🇬🇧', 'GB': '🇬🇧', 'Britain': '🇬🇧', 'England': '🇬🇧',
  'Canada': '🇨🇦', 'CA': '🇨🇦',
  'Australia': '🇦🇺', 'AU': '🇦🇺',
  'Hong Kong': '🇭🇰', 'HK': '🇭🇰',
  'Singapore': '🇸🇬', 'SG': '🇸🇬',
  'Japan': '🇯🇵', 'JP': '🇯🇵',
  'South Korea': '🇰🇷', 'KR': '🇰🇷', 'Korea': '🇰🇷',
  'Germany': '🇩🇪', 'DE': '🇩🇪',
  'France': '🇫🇷', 'FR': '🇫🇷',
  'Netherlands': '🇳🇱', 'NL': '🇳🇱',
  'Switzerland': '🇨🇭', 'CH': '🇨🇭',
  'Sweden': '🇸🇪', 'SE': '🇸🇪',
  'Italy': '🇮🇹', 'IT': '🇮🇹',
  'Spain': '🇪🇸', 'ES': '🇪🇸',
  'New Zealand': '🇳🇿', 'NZ': '🇳🇿',
  'Ireland': '🇮🇪', 'IE': '🇮🇪',
  'China': '🇨🇳', 'CN': '🇨🇳',
  'Macau': '🇲🇴', 'MO': '🇲🇴',
  'Taiwan': '🇹🇼', 'TW': '🇹🇼',
};

export function countryFlag(country?: string): string {
  if (!country) return '🌐';
  return COUNTRY_FLAG[country] || '🌐';
}
