'use client';

/**
 * SchoolPicker — 院校下拉选择器 (通用组件)
 *
 * 功能:
 *  - 输入学校名 → 250ms 防抖搜索
 *  - 支持中英文 + 拼音首字母 (如 bjqgz → 北京青古宅中学)
 *  - 按学历自动过滤 (高中→high_school, 本/硕/博→university 等)
 *  - 实时下拉候选, Enter 选中, 第一个高亮
 *  - 选中存 school_id (业务编码)
 *  - 已选后显示 school_prestige (顶尖/一流/...) + 详细卡片
 *  - 可选 compare mode: 添加 1-3 个候选对比
 *
 * 用法:
 *   <SchoolPicker
 *     value={form.current_school}
 *     schoolId={form.current_school_id}
 *     eduLevel={form.current_edu_level}  // 'high_school' | 'vocational_college' | 'university'
 *     onChange={(school) => updateForm('current_school', school.name_cn)}
 *     onIdChange={(id) => updateForm('current_school_id, id)}
 *     onDetailChange={(detail) => setSelectedSchoolDetail(detail)}
 *   />
 */

import { useState, useEffect, useRef } from 'react';
import { Search, Loader2, X, GraduationCap } from 'lucide-react';

export interface SchoolItem {
  school_id: string;
  name_cn?: string;
  name_en?: string;
  cn_province_code?: string;
  cn_category_code?: string;
  region?: string;
  ranking_qs?: number;
  ranking_the?: number;
  tuition_intl?: number;
  currency?: string;
  school_type?: string;
}

export interface SchoolPickerProps {
  value: string;
  schoolId?: string;
  eduLevel?: string;             // 当前学历 (决定 category 过滤)
  cnMajorSlug?: string;          // (未来扩展) 已选专业, 可按 major 过滤
  placeholder?: string;
  disabled?: boolean;
  onChange: (name: string) => void;  // name_cn 变化
  onIdChange?: (id: string) => void;
  onDetailChange?: (detail: SchoolItem | null) => void;
  showDetailCard?: boolean;       // 是否显示已选学校详情 (声望+排名+学费)
  showCompareTool?: boolean;      // 是否显示"学校对比"工具
  apiBase?: string;               // 默认 '/api/assessment' (SOHO 代理)
  className?: string;
}

export function SchoolPicker({
  value,
  schoolId,
  eduLevel = 'university',  // 默认英文枚举 (R24 修复, 同时兼容中文字符串)
  cnMajorSlug,
  placeholder = '输入学校名称, 例: 中国地质 / 清华 / 北大 / qhdx / Stanford',
  disabled = false,
  onChange,
  onIdChange,
  onDetailChange,
  showDetailCard = true,
  showCompareTool = false,
  apiBase = '/api/assessment',
  className = '',
}: SchoolPickerProps) {
  const [query, setQuery] = useState(value || '');
  const [results, setResults] = useState<SchoolItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [highlightedIdx, setHighlightedIdx] = useState(0);
  const [detail, setDetail] = useState<SchoolItem | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [compareList, setCompareList] = useState<SchoolItem[]>([]);
  const timerRef = useRef<any>(null);

  // 同步外部 value
  useEffect(() => {
    setQuery(value || '');
  }, [value]);

  // 选中后自动加载完整详情
  useEffect(() => {
    if (schoolId && schoolId !== detail?.school_id) {
      loadDetail(schoolId);
    } else if (!schoolId && detail) {
      setDetail(null);
    }
  }, [schoolId]);

  // 暴露 detail 到外部
  useEffect(() => {
    onDetailChange?.(detail);
  }, [detail]);

  // 防抖搜索
  useEffect(() => {
    clearTimeout(timerRef.current);
    if (!query.trim()) {
      setResults([]);
      return;
    }
    timerRef.current = setTimeout(() => {
      doSearch(query);
    }, 250);
  }, [query]);

  async function doSearch(q: string) {
    setSearching(true);
    setShowDropdown(true);
    try {
      const params = new URLSearchParams();
      params.set('q', q);
      // 按学历自动过滤 (eduLevel 兼容中英文: '高中'/'high_school' 都映射到 high_school)
      // R24 (2026-07-17): 修复中文/英文类型不匹配导致的“选择高中后输大学名查不到”bug
      const cat =
        eduLevel === 'high_school' || eduLevel === '高中' ? 'high_school' :
        eduLevel === 'vocational_college' || eduLevel === '中职/中专' || eduLevel === '高职/大专' ? 'vocational_college' :
        'university';  // 本科/硕士/博士/其他
      params.set('cn_category', cat);
      const resp = await fetch(`${apiBase}/schools/lookup?${params}`);
      const data = await resp.json();
      setResults((data.items || []).slice(0, 20));
    } catch (e) {
      console.warn('school search failed', e);
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  async function loadDetail(id: string) {
    setDetailLoading(true);
    try {
      const resp = await fetch(`${apiBase}/schools/${encodeURIComponent(id)}`);
      if (resp.ok) {
        const d = await resp.json();
        setDetail(d);
      }
    } catch (e) {
      console.warn('school detail failed', e);
    } finally {
      setDetailLoading(false);
    }
  }

  function selectSchool(school: SchoolItem) {
    onChange(school.name_cn || school.name_en || '');
    onIdChange?.(school.school_id);
    setQuery(school.name_cn || school.name_en || '');
    setShowDropdown(false);
  }

  function clearSchool() {
    onChange('');
    onIdChange?.('');
    setDetail(null);
    setQuery('');
    setResults([]);
    setShowDropdown(false);
  }

  // 学校声望 (根据 ranking_qs 推)
  function getPrestige(s: SchoolItem): { color: string; label: string; note: string } | null {
    if (!s.ranking_qs) return null;
    const rqs = s.ranking_qs;
    const isCN = s.cn_category_code === 'university' || s.cn_category_code === 'high_school' ||
                 s.cn_category_code === 'vocational_college' || s.cn_category_code === 'vocational_university';
    if (isCN) {
      if (rqs <= 30) return { color: 'success', label: '顶尖名校', note: 'C9 联盟级别, 申请任何项目都有优势' };
      if (rqs <= 100) return { color: 'success', label: '985 顶尖', note: '985 院校 Top 100, 申请有优势' };
      if (rqs <= 200) return { color: 'info', label: '985/211', note: '可申请大部分研究生项目' };
      if (rqs <= 500) return { color: 'info', label: '知名大学', note: '知名度好, 部分项目可申请' };
      return { color: 'warning', label: '普通院校', note: '需靠 GPA/科研 补强' };
    }
    // 海外
    if (rqs <= 10) return { color: 'success', label: '世界顶尖', note: '全球 Top 10, 顶尖留学目标' };
    if (rqs <= 50) return { color: 'success', label: '世界一流', note: '全球 Top 50, 一流留学目标' };
    if (rqs <= 200) return { color: 'info', label: '世界知名', note: '全球 Top 200, 优秀留学目标' };
    if (rqs <= 500) return { color: 'info', label: '世界认可', note: '全球 Top 500, 良好留学目标' };
    return { color: 'warning', label: '待了解', note: '排名一般, 建议查清认证' };
  }

  const prestige = detail ? getPrestige(detail) : null;

  return (
    <div className={`relative ${className}`}>
      {/* 输入框 + 搜索图标 */}
      <div className="relative">
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            onChange(e.target.value);
            setHighlightedIdx(0);  // 搜索时重置高亮
          }}
          onFocus={() => setShowDropdown(true)}
          onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
          onKeyDown={(e) => {
            // R17 (2026-07-16): 键盘上下箭头 + Enter 选择
            if (!showDropdown || results.length === 0) return;
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              setHighlightedIdx((i) => Math.min(results.length - 1, i + 1));
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              setHighlightedIdx((i) => Math.max(0, i - 1));
            } else if (e.key === 'Enter') {
              e.preventDefault();
              const sel = results[highlightedIdx];
              if (sel) selectSchool(sel);
            } else if (e.key === 'Escape') {
              setShowDropdown(false);
            }
          }}
          type="text"
          placeholder={placeholder}
          disabled={disabled}
          className="w-full border border-gray-300 rounded-lg px-4 py-3 pr-10 focus:ring-2 focus:ring-primary-500 focus:outline-none disabled:bg-gray-100"
        />
        {searching ? (
          <Loader2 className="absolute right-3 top-3 w-5 h-5 text-gray-400 animate-spin" />
        ) : (
          <Search className="absolute right-3 top-3 w-5 h-5 text-gray-400" />
        )}
        {schoolId && (
          <button
            type="button"
            onClick={clearSchool}
            className="absolute right-10 top-3 text-gray-400 hover:text-red-500"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* 下拉候选 */}
      {showDropdown && query && (
        <div className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {results.length > 0 ? (
            results.map((s, idx) => {
              // R17 (2026-07-16): 高亮键盘选中 + 显示学校类型徽章
              const isHighlighted = idx === highlightedIdx;
              const isMainCampus = !s.name_cn?.includes('(') && !s.name_cn?.includes('深圳') && !s.name_cn?.includes('研究院') && !s.name_cn?.includes('学院') && !s.name_cn?.includes('分校');
              return (
                <div
                  key={s.school_id}
                  onMouseDown={() => selectSchool(s)}
                  onMouseEnter={() => setHighlightedIdx(idx)}
                  className={`px-4 py-2.5 cursor-pointer border-b border-gray-100 last:border-0 flex items-center justify-between transition-colors ${
                    isHighlighted ? 'bg-primary-50 border-l-4 border-l-primary-500' : 'hover:bg-gray-50'
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 truncate">{s.name_cn || s.name_en}</span>
                      {isMainCampus && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-emerald-100 text-emerald-700 rounded shrink-0">主校区</span>
                      )}
                      {s.cn_category_code === '985' && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-red-100 text-red-700 rounded shrink-0">985</span>
                      )}
                      {s.cn_category_code === '211' && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-orange-100 text-orange-700 rounded shrink-0">211</span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {s.region}{s.cn_category_code && ` · ${s.cn_category_code}`}
                      {s.ranking_qs && ` · QS #${s.ranking_qs}`}
                    </div>
                  </div>
                  {isHighlighted && (
                    <span className="text-xs text-primary-600 font-medium shrink-0 ml-2">↵ 选中</span>
                  )}
                </div>
              );
            })
          ) : !searching ? (
            <div className="p-4 text-center text-gray-500 text-sm">
              未找到匹配学校, 试试拼音首字母 (如 bjqgz)
            </div>
          ) : null}
        </div>
      )}

      {/* 已选学校详情卡片 */}
      {showDetailCard && schoolId && (
        <div className="mt-2 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg text-sm">
          {detailLoading ? (
            <div className="text-gray-500 text-center py-2">⏳ 加载学校详情...</div>
          ) : detail ? (
            <div>
              <div className="flex items-start gap-3">
                <GraduationCap className="w-5 h-5 text-primary-600 shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="font-medium text-gray-900">{detail.name_cn || detail.name_en}</span>
                    {detail.ranking_qs && (
                      <span className="text-xs px-1.5 py-0.5 bg-primary-100 text-primary-700 rounded">QS #{detail.ranking_qs}</span>
                    )}
                    {detail.ranking_the && (
                      <span className="text-xs px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded">THE #{detail.ranking_the}</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500">
                    {detail.region}
                    {detail.school_type && (
                      <span className="ml-2 px-1.5 py-0.5 bg-gray-100 rounded">
                        {detail.school_type === 'public' ? '公立' : detail.school_type === 'private' ? '私立' : detail.school_type}
                      </span>
                    )}
                  </div>
                  {prestige && (
                    <div className="mt-1 flex items-center gap-2">
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${
                          prestige.color === 'success' ? 'bg-green-100 text-green-700' :
                          prestige.color === 'info' ? 'bg-blue-100 text-blue-700' :
                          prestige.color === 'warning' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-red-100 text-red-700'
                        }`}
                      >
                        {prestige.label}
                      </span>
                      <span className="text-xs text-gray-600">{prestige.note}</span>
                    </div>
                  )}
                  {detail.tuition_intl && (
                    <div className="mt-1 text-xs text-success-600">
                      💰 学费: {detail.tuition_intl.toLocaleString()} {detail.currency || 'USD'}/年
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* 学校对比工具 (可选) */}
      {showCompareTool && schoolId && (
        <div className="mt-3 p-3 bg-purple-50 border border-purple-200 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-medium text-purple-800 flex items-center gap-1">
              <span>🆚</span><span>学校对比 (添加 {compareList.length}/3 个)</span>
            </p>
            {compareList.length > 0 && (
              <button type="button" onClick={() => setCompareList([])} className="text-xs text-purple-600 hover:underline">清空</button>
            )}
          </div>
          {compareList.length > 0 && (
            <div className="mb-2 space-y-1">
              {compareList.map((c) => (
                <div key={c.school_id} className="flex items-center justify-between bg-white rounded px-2 py-1 text-xs">
                  <div className="flex-1 min-w-0">
                    <span className="font-medium text-gray-800">{c.name_cn || c.name_en}</span>
                    {c.region && <span className="text-gray-500 ml-1">({c.region})</span>}
                    {c.ranking_qs && <span className="text-orange-600 ml-1">QS#{c.ranking_qs}</span>}
                    {c.tuition_intl && <span className="text-success-600 ml-1">💰{c.tuition_intl}{c.currency || 'USD'}</span>}
                  </div>
                  <button type="button" onClick={() => setCompareList(compareList.filter(x => x.school_id !== c.school_id))} className="text-red-400 hover:text-red-600 ml-1">✕</button>
                </div>
              ))}
            </div>
          )}
          {compareList.length < 3 && (
            <CompareSchoolInput
              onAdd={async (school) => {
                try {
                  const resp = await fetch(`${apiBase}/schools/${encodeURIComponent(school.school_id)}`);
                  if (resp.ok) {
                    const d = await resp.json();
                    if (compareList.length >= 3) compareList.shift();
                    setCompareList([...compareList, d]);
                  } else {
                    setCompareList([...compareList, school]);
                  }
                } catch (e) {
                  setCompareList([...compareList, school]);
                }
              }}
              cnCategory={
                eduLevel === 'high_school' || eduLevel === '高中' ? 'high_school' :
                eduLevel === 'vocational_college' || eduLevel === '中职/中专' || eduLevel === '高职/大专' ? 'vocational_college' :
                'university'
              }
              apiBase={apiBase}
            />
          )}
        </div>
      )}
    </div>
  );
}

// 子组件: 添加对比学校输入 (复用同样的搜索逻辑)
function CompareSchoolInput({ onAdd, cnCategory, apiBase }: { onAdd: (s: SchoolItem) => void; cnCategory: string; apiBase: string }) {
  const [q, setQ] = useState('');
  const [results, setResults] = useState<SchoolItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [highlightedIdx, setHighlightedIdx] = useState(0);
  const timerRef = useRef<any>(null);

  useEffect(() => {
    clearTimeout(timerRef.current);
    if (!q.trim()) {
      setResults([]);
      return;
    }
    timerRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const params = new URLSearchParams();
        params.set('q', q);
        params.set('cn_category', cnCategory);
        const resp = await fetch(`${apiBase}/schools/lookup?${params}`);
        const data = await resp.json();
        setResults((data.items || []).slice(0, 5));
      } catch (e) {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 250);
  }, [q]);

  return (
    <div className="relative">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => setShowDropdown(true)}
        onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
        type="text"
        placeholder="搜索候选学校 (中英文)..."
        className="w-full border border-purple-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-purple-400 focus:outline-none bg-white"
      />
      {searching && <span className="absolute right-2 top-1.5 text-purple-400 text-[10px]">搜索中...</span>}
      {showDropdown && results.length > 0 && (
        <div className="absolute z-20 mt-1 w-full bg-white border border-purple-200 rounded shadow-lg max-h-40 overflow-y-auto">
          {results.map((cs) => (
            <div
              key={cs.school_id}
              onMouseDown={() => {
                onAdd(cs);
                setQ('');
                setResults([]);
                setShowDropdown(false);
              }}
              className="px-2 py-1 hover:bg-purple-50 cursor-pointer text-xs border-b border-gray-100 last:border-0"
            >
              <div className="font-medium text-gray-800">{cs.name_cn || cs.name_en}</div>
              <div className="text-gray-500 text-[10px]">{cs.region} · {cs.cn_category_code}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default SchoolPicker;