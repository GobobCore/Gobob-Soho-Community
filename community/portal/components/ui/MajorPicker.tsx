'use client';

/**
 * MajorPicker — 院校专业选择器 (通用组件, 对称 SchoolPicker)
 *
 * 功能:
 *  - 从 /api/portal/majors 拉专业列表 (52 个, 全量加载)
 *  - 支持中英文 + 子专业二级联动
 *  - 选中存 slug (业务编码)
 *  - 显示"待定/智能推荐"选项 (后端会推荐相近专业)
 *
 * 用法:
 *   <MajorPicker
 *     value={form.target_major}
 *     slug={form.target_major_slug}
 *     placeholder="如：计算机科学"
 *     onChange={(name) => updateForm('target_major', name)}
 *     onSlugChange={(slug) => updateForm('target_major_slug', slug)}
 *     onUncertainChange={(u) => updateForm('target_major_uncertain', u)}
 *   />
 */

import { useState, useEffect, useMemo, useRef } from 'react';
import { Search, Loader2, X, BookOpen, Lightbulb, ChevronRight } from 'lucide-react';

export interface MajorItem {
  slug: string;
  name_cn?: string;
  name_en?: string;
  category?: string;
  field?: string;
  parent_slug?: string;
  degree_levels?: string[];
  salary_range?: string;
  desc_short?: string;
  view_count?: number;
  top_schools?: any[];
  career_paths?: any[];
}

export interface MajorPickerProps {
  value: string;                  // 选中的专业名 (name_cn)
  slug?: string;                  // 选中的专业 slug (业务编码)
  placeholder?: string;
  disabled?: boolean;
  onChange: (name: string) => void;
  onSlugChange?: (slug: string) => void;
  onUncertainChange?: (uncertain: boolean) => void;
  showDetailCard?: boolean;       // 是否显示已选专业详情
  showSubMajors?: boolean;        // 是否显示子专业二级联动
  apiBase?: string;               // 默认 '/api/assessment' (SOHO 代理)
  className?: string;
}

export function MajorPicker({
  value,
  slug,
  placeholder = '输入专业名称 (中英文)',
  disabled = false,
  onChange,
  onSlugChange,
  onUncertainChange,
  showDetailCard = true,
  showSubMajors = true,
  apiBase = '/api/assessment',
  className = '',
}: MajorPickerProps) {
  const [allMajors, setAllMajors] = useState<MajorItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState(value || '');
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedMajor, setSelectedMajor] = useState<MajorItem | null>(null);
  const [subMajors, setSubMajors] = useState<MajorItem[]>([]);
  const [subLoading, setSubLoading] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const fetchedRef = useRef(false);

  // 同步外部 value
  useEffect(() => {
    setQuery(value || '');
  }, [value]);

  // 一次性加载所有专业
  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    loadAllMajors();
  }, []);

  // 选中后加载详情
  useEffect(() => {
    if (slug && allMajors.length > 0) {
      const m = allMajors.find((x) => x.slug === slug);
      if (m) {
        setSelectedMajor(m);
        // 如果是顶级专业, 加载子专业
        if (showSubMajors && !m.parent_slug) {
          loadSubMajors(slug);
        }
      }
    } else {
      setSelectedMajor(null);
      setSubMajors([]);
    }
  }, [slug, allMajors, showSubMajors]);

  // 暴露 uncertain
  useEffect(() => {
    onUncertainChange?.(uncertain);
  }, [uncertain]);

  async function loadAllMajors() {
    setLoading(true);
    try {
      const resp = await fetch(`${apiBase}/majors?limit=200`);
      const data = await resp.json();
      setAllMajors(data.items || []);
    } catch (e) {
      console.warn('majors load failed', e);
      setAllMajors([]);
    } finally {
      setLoading(false);
    }
  }

  async function loadSubMajors(parent_slug: string) {
    setSubLoading(true);
    try {
      const resp = await fetch(`${apiBase}/majors?parent_slug=${encodeURIComponent(parent_slug)}&limit=50`);
      const data = await resp.json();
      setSubMajors(data.items || []);
    } catch (e) {
      console.warn('sub majors load failed', e);
      setSubMajors([]);
    } finally {
      setSubLoading(false);
    }
  }

  // 过滤顶级专业 (parent_slug IS NULL)
  const topLevelMajors = useMemo(
    () => allMajors.filter((m) => !m.parent_slug),
    [allMajors]
  );

  // 搜索过滤
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return topLevelMajors;
    return topLevelMajors.filter(
      (m) =>
        (m.name_cn || '').toLowerCase().includes(q) ||
        (m.name_en || '').toLowerCase().includes(q)
    );
  }, [query, topLevelMajors]);

  function selectMajor(m: MajorItem) {
    onChange(m.name_cn || m.name_en || '');
    onSlugChange?.(m.slug);
    setUncertain(false);
    setShowDropdown(false);
    setQuery(m.name_cn || m.name_en || '');
  }

  function selectSubMajor(sm: MajorItem) {
    onChange(sm.name_cn || sm.name_en || '');
    onSlugChange?.(sm.slug);
    setUncertain(false);
    setShowDropdown(false);
    setQuery(sm.name_cn || sm.name_en || '');
  }

  function setUncertainFn() {
    setUncertain(true);
    onChange('待定');
    onSlugChange?.('');
    setShowDropdown(false);
    setQuery('');
  }

  function clearMajor() {
    setUncertain(false);
    onChange('');
    onSlugChange?.('');
    setSelectedMajor(null);
    setSubMajors([]);
    setQuery('');
    setShowDropdown(false);
  }

  return (
    <div className={`relative ${className}`}>
      {/* 输入框 + 搜索图标 */}
      <div className="relative">
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            onChange(e.target.value);
            setUncertain(false);
          }}
          onFocus={() => setShowDropdown(true)}
          onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
          type="text"
          placeholder={placeholder}
          disabled={disabled}
          className="w-full border border-gray-300 rounded-lg px-4 py-3 pr-10 focus:ring-2 focus:ring-primary-500 focus:outline-none disabled:bg-gray-100"
        />
        {loading ? (
          <Loader2 className="absolute right-3 top-3 w-5 h-5 text-gray-400 animate-spin" />
        ) : (
          <Search className="absolute right-3 top-3 w-5 h-5 text-gray-400" />
        )}
        {(slug || uncertain) && (
          <button
            type="button"
            onClick={clearMajor}
            className="absolute right-10 top-3 text-gray-400 hover:text-red-500"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* 下拉候选 */}
      {showDropdown && (
        <div className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {filtered.length > 0 ? (
            filtered.map((m, idx) => (
              <div
                key={m.slug}
                onMouseDown={() => selectMajor(m)}
                className={`px-4 py-2 hover:bg-primary-50 cursor-pointer border-b border-gray-100 last:border-0 ${idx === 0 ? 'bg-blue-50' : ''}`}
              >
                <div className="font-medium text-gray-900">{m.name_cn || m.name_en}</div>
                <div className="text-xs text-gray-500">
                  {m.name_en} · {m.category}
                  {m.salary_range && <span className="ml-2 text-success-600">💰 {m.salary_range}</span>}
                </div>
              </div>
            ))
          ) : !loading ? (
            <div className="p-4">
              <p className="text-center text-gray-500 text-sm mb-3">未在标准库找到</p>
              <div className="flex gap-2 justify-center">
                <button
                  type="button"
                  onMouseDown={() => { clearMajor(); setShowDropdown(false); }}
                  className="px-3 py-1 text-xs border rounded hover:bg-gray-50"
                >
                  手动保留
                </button>
                <button
                  type="button"
                  onMouseDown={() => { setUncertainFn(); setShowDropdown(false); }}
                  className="px-3 py-1 text-xs border rounded bg-warning-100 text-warning-700 hover:bg-warning-200 flex items-center gap-1"
                >
                  <Lightbulb className="w-3 h-3" />
                  智能推荐
                </button>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* 智能推荐/待定提示 */}
      {uncertain && (
        <p className="text-xs text-warning-600 mt-1 flex items-center gap-1">
          <Lightbulb className="w-3 h-3" />
          未确定, 将根据国家+预算智能推荐相近专业
        </p>
      )}

      {/* 二级专业 (选了顶级专业后) */}
      {showSubMajors && selectedMajor && !selectedMajor.parent_slug && subMajors.length > 0 && (
        <div className="mt-3 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
          <p className="text-xs text-blue-700 mb-2 flex items-center gap-1">
            <BookOpen className="w-3 h-3" />
            {selectedMajor.name_cn} 的细分方向 (点击选择)
          </p>
          <div className="flex flex-wrap gap-1.5">
            {subMajors.map((sm) => (
              <button
                key={sm.slug}
                type="button"
                onClick={() => selectSubMajor(sm)}
                className={`px-2.5 py-1 text-xs border rounded-full transition ${
                  slug === sm.slug
                    ? 'border-primary-500 bg-primary-500 text-white'
                    : 'border-blue-300 bg-white text-blue-700 hover:bg-blue-100'
                }`}
              >
                {sm.name_cn}
                {sm.salary_range && <span className="ml-1 opacity-75">💰</span>}
              </button>
            ))}
          </div>
          {subLoading && <p className="text-xs text-blue-500 mt-1">加载中...</p>}
        </div>
      )}

      {/* 已选专业详情卡片 */}
      {showDetailCard && selectedMajor && (
        <div className="mt-2 p-3 bg-gradient-to-r from-amber-50 to-yellow-50 border border-amber-200 rounded-lg text-sm">
          <div className="flex items-start gap-3">
            <BookOpen className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="font-bold text-gray-900">{selectedMajor.name_cn}</span>
                {selectedMajor.category && (
                  <span className="text-xs px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">
                    {selectedMajor.category}
                  </span>
                )}
                <span v-if="selectedMajor.field" className="text-xs px-1.5 py-0.5 bg-gray-100 rounded">
                  {selectedMajor.field}
                </span>
              </div>
              {selectedMajor.name_en && (
                <p className="text-xs text-gray-500 mb-1">{selectedMajor.name_en}</p>
              )}
              {selectedMajor.salary_range && (
                <p className="text-xs text-success-600">💰 就业 {selectedMajor.salary_range}</p>
              )}
              {selectedMajor.desc_short && (
                <p className="text-xs text-gray-600 mt-1 line-clamp-2">{selectedMajor.desc_short}</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MajorPicker;