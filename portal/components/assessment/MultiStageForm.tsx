/**
 * MultiStageForm — 智能评估多步表单 (R13 2026-07-16)
 *
 * 6 步评估 (替代原 777 行 page.tsx 表单):
 *   Step 1: 当前学段 (high_school/undergraduate/graduate_master/working_...)
 *   Step 2: 当前院校 + 专业 (SchoolPicker 自动判定 tier)
 *   Step 3: 留学目标 (国家多选 + 学位联动 + 申请季)
 *   Step 4: 语言 + 标化 (按国家自动给对应考试)
 *   Step 5: 软背景 (科研/实习/竞赛/志愿/作品集)
 *   Step 6: 预算 + 偏好
 *
 * 特点:
 *   - Step progress 进度条
 *   - 数据来自 /assessment-meta 端点 (R12)
 *   - 选国家后自动更新语言考试项
 *   - 选学段后自动更新可申学位
 *   - 院校下拉自动判定 985/211/海外
 *   - localStorage 自动保存 (Q28)
 */

'use client';

import { useState, useEffect } from 'react';
import {
  GraduationCap, MapPin, BookOpen, Languages, Sparkles, Wallet,
  ChevronRight, ChevronLeft, CheckCircle2, AlertCircle, Loader2,
  School, Award, Briefcase, Trophy, Heart, Palette, Globe,
} from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { SchoolPicker } from '@/components/ui/SchoolPicker';
import { MajorPicker } from '@/components/ui/MajorPicker';

// ─── 类型 ────────────────────────────────────────────────────────
type CountryMeta = {
  id: string;
  iso: string;
  name_cn: string;
  flag?: string;
  primary_language: string;
  english_required: boolean;
  english_tests?: string;
  local_test?: string;
  local_required: boolean;
  standardized_tests?: string;
  notes?: string;
};

type DisciplineMeta = {
  code: string;
  name_zh: string;
  name_en: string;
};

type SchoolTier = { code: string; name_cn: string; weight: number };

type MetaData = {
  countries: CountryMeta[];
  stage_map: Record<string, Array<{ degree: string; min_years: number; notes?: string }>>;
  disciplines: DisciplineMeta[];
  school_tiers: SchoolTier[];
};

// 6 步骤
const STEPS = [
  { id: 1, name: '学段', icon: GraduationCap, desc: '你现在在读什么?' },
  { id: 2, name: '院校', icon: School, desc: '在哪读书?' },
  { id: 3, name: '留学目标', icon: MapPin, desc: '想去哪些国家? 什么学位?' },
  { id: 4, name: '语言', icon: Languages, desc: '英语/小语种成绩' },
  { id: 5, name: '软背景', icon: Sparkles, desc: '科研 / 实习 / 竞赛' },
  { id: 6, name: '预算', icon: Wallet, desc: '预算 + 偏好' },
] as const;

// R23 (2026-07-17): 移除 working_other (在职 MBA/移民/探亲) - 算法空集
// 学段合并 - 5 大类 + 子状态
type StageGroup = 'high_school' | 'vocational' | 'undergraduate' | 'graduate_master' | 'graduate_phd';

const STAGE_GROUP_LABELS: Record<StageGroup, string> = {
  high_school: '高中',
  vocational: '专科',
  undergraduate: '本科',
  graduate_master: '硕士',
  graduate_phd: '博士',
};

// 内部完整分类 (9 种) - 大类 5 大 + 毕业子状态
const STAGE_LABELS: Record<string, string> = {
  high_school: '高中生在读',
  high_school_grad: '高中已毕业',
  vocational: '专科在读',
  vocational_grad: '专科已毕业',
  undergraduate: '本科生在读',
  undergraduate_grad: '本科已毕业',
  graduate_master: '硕士生在读',
  graduate_master_grad: '硕士已毕业',
  graduate_phd: '博士生在读',
};

// 大类 → 子状态列表
const STAGE_SUBSTATES: Record<StageGroup, Array<{ code: string; label: string }>> = {
  high_school: [
    { code: 'high_school', label: '高一' },
    { code: 'high_school', label: '高二' },
    { code: 'high_school', label: '高三' },
    { code: 'high_school_grad', label: '已毕业' },
  ],
  vocational: [
    { code: 'vocational', label: '大一' },
    { code: 'vocational', label: '大二' },
    { code: 'vocational', label: '大三' },
    { code: 'vocational_grad', label: '已毕业' },
  ],
  undergraduate: [
    { code: 'undergraduate', label: '大一' },
    { code: 'undergraduate', label: '大二' },
    { code: 'undergraduate', label: '大三' },
    { code: 'undergraduate', label: '大四' },
    { code: 'undergraduate_grad', label: '已毕业' },
  ],
  graduate_master: [
    { code: 'graduate_master', label: '研一' },
    { code: 'graduate_master', label: '研二' },
    { code: 'graduate_master', label: '研三' },
    { code: 'graduate_master_grad', label: '已毕业' },
  ],
  graduate_phd: [
    { code: 'graduate_phd', label: '博一' },
    { code: 'graduate_phd', label: '博二' },
    { code: 'graduate_phd', label: '博三' },
    { code: 'graduate_phd', label: '博四及以上' },
  ],
};

// 当前 stage_code → 大类 (Step 1 显示用)
const STAGE_TO_GROUP: Record<string, StageGroup> = {
  high_school: 'high_school',
  high_school_grad: 'high_school',
  vocational: 'vocational',
  vocational_grad: 'vocational',
  undergraduate: 'undergraduate',
  undergraduate_grad: 'undergraduate',
  graduate_master: 'graduate_master',
  graduate_master_grad: 'graduate_master',
  graduate_phd: 'graduate_phd',
};

// ─── Props ────────────────────────────────────────────────────────
export type MultiStageFormData = {
  // Step 1
  current_stage: string;
  current_stage_year?: string;  // 高三 / 大三 / 研二
  // Step 2
  current_school_id?: string;
  current_school_name?: string;
  current_school_tier?: string;
  current_major?: string;
  gpa?: number;
  gpa_scale?: string;
  // Step 3
  target_countries: string[];
  target_degree: string;
  target_intake: string;  // 2026 Fall / 2027 Spring
  target_major: string;
  // Step 4
  english_test?: string;  // TOEFL/IELTS/PTE/...
  english_score?: number;
  // R46 (R42 P0-4): 英语小分 (G5 要求单项 ≥6.5/7.0)
  english_sub_reading?: number;   // 雅思 / 托福 Reading
  english_sub_listening?: number; // Listening
  english_sub_speaking?: number;  // Speaking
  english_sub_writing?: number;   // Writing
  // R47 (R42 P1-1): 接受 path 路径 (Foundation/Diploma/2+2)
  accept_pathway?: boolean;
  // R48 (R42 P1-2): 课外活动 / 国际交流
  extracurricular?: string[];       // 学生会/社团/学科外活动/志愿者等
  international_exchange?: boolean;  // 海外夏校/交换/短期项目
  international_exchange_top?: boolean;  // 是否顶尖项目 (RSI/SSP 等)
  local_tests?: Record<string, string>;  // {JP: 'JLPT N1', ...}
  standardized_tests?: Record<string, number>;  // {GRE: 320, GMAT: 720, SAT: 1500, ACT: 33, AP_count: 5, LSAT: 170, MCAT: 518}
  // Step 5
  research_exp: number;
  internship_exp: number;
  competition?: string[];        // 学科竞赛 (奥赛/AMC)
  other_competition?: string[];  // 其他竞赛 (商赛/挑战杯) — 与 competition 独立, 互不联动
  volunteer?: string[];          // 志愿者/公益
  // R35: 顶尖夏校 + 学生组织 独立字段 (避免与 volunteer 互污染)
  summer_camp?: string[];
  student_org?: string[];
  portfolio?: boolean;
  publications?: number;
  // P4.3 (2026-07-19): 跨专业 / 第二学位
  is_cross_disciplinary?: boolean;
  current_major_category?: string;
  target_major_category?: string;
  prerequisite_completed?: boolean;
  has_second_degree?: boolean;
  second_degree_field?: string;
  lor_status?: string;  // R32: 推荐信准备状态
  // R45 (R42 P0-3): MBA + PhD 专项
  work_years?: number;        // 毕业后工作年限 (MBA 必填, PhD 必填 0)
  contact_status?: string;     // 套磁状态 (PhD 必填): 'not_started' | 'emailed' | 'received_reply' | 'invited' | 'accepted'
  // Step 6 - R43 拆分成 tuition + living 分离
  budget_min: number;          // 学费下限 (万/年)
  budget_max: number;          // 学费上限 (万/年)
  living_min?: number;         // 生活费下限 (万/年)
  living_max?: number;         // 生活费上限 (万/年)
  scholarship_needed?: boolean;
  funding_source?: string;     // 资金来源: parents / scholarship / loan / self
  campus_preference?: string;  // urban/rural/suburban
  school_size?: string;  // large/medium/small
  // P3.9-4 (2026-07-18): PhD 套磁 + 推荐信
  advisor_contacted?: boolean;
  recommendation_level?: string;
};

type Props = {
  onSubmit: (data: MultiStageFormData) => Promise<void>;
  loading: boolean;
  initialData?: Partial<MultiStageFormData>;
  onTrack?: (eventName: string, data?: Record<string, any>) => void;
  // R21 (2026-07-16): 实时数据回调 (让 page.tsx 显示算法说明)
  onDataChange?: (data: MultiStageFormData) => void;
  // Bug-fix (2026-07-20): R21 重置修复 — 抑制初始 onDataChange 调用
  //   重置表单时, MultiStageForm 会 remount, 默认会发送默认值给 page.tsx
  //   这会重新点亮 R21 块, 让「全部评估数据项」仍显示默认值 (被误认为历史数据)
  //   传 true 跳过初始 useEffect, 重置后 R21 块保持隐藏, 直到用户开始填表
  suppressInitialOnDataChange?: boolean;
};

// R37 (2026-07-17): BFF_BASE_URL 使用相对路径 (让 Next.js proxy 路由)
// BFF_BASE_URL 用相对路径（空字符串），浏览器发到当前 host，由 Next.js rewrite 代理 /api/* 到后端
// // Next.js rewrite 把 /api/* 代理到后端
const BFF_BASE_URL =
  typeof process !== 'undefined' && process.env.PORTAL_BACKEND_URL
    ? process.env.PORTAL_BACKEND_URL
    : '';

// R30 (2026-07-17): 动态计算可申学位 + 申请季选项
// 设计原则:
// 1. 不依赖 meta API 加载 (避免 “默认” 选项) — fallback 内置
// 2. 申请季要根据 current_stage + current_stage_year 动态生成
//    (高一/大二学生 需 远期规划, 不应只到 2027)
// 3. 高中在读: 可申 Bachelor / Foundation / Diploma, 不应出现 Master

// R31 (2026-07-17): meta 未加载时 fallback 国家, 避免 grid 空白空局
const FALLBACK_COUNTRIES: CountryMeta[] = [
  { id: 'US', iso: 'US', name_cn: '美国', flag: 'us', primary_language: 'English', english_required: true, local_required: false },
  { id: 'UK', iso: 'GB', name_cn: '英国', flag: 'gb', primary_language: 'English', english_required: true, local_required: false },
  { id: 'CA', iso: 'CA', name_cn: '加拿大', flag: 'ca', primary_language: 'English', english_required: true, local_required: false },
  { id: 'AU', iso: 'AU', name_cn: '澳大利亚', flag: 'au', primary_language: 'English', english_required: true, local_required: false },
  { id: 'HK', iso: 'HK', name_cn: '香港', flag: 'hk', primary_language: 'Cantonese', english_required: true, local_required: false },
  { id: 'SG', iso: 'SG', name_cn: '新加坡', flag: 'sg', primary_language: 'English', english_required: true, local_required: false },
  { id: 'JP', iso: 'JP', name_cn: '日本', flag: 'jp', primary_language: 'Japanese', english_required: false, local_required: false },
  { id: 'KR', iso: 'KR', name_cn: '韩国', flag: 'kr', primary_language: 'Korean', english_required: false, local_required: false },
  { id: 'FR', iso: 'FR', name_cn: '法国', flag: 'fr', primary_language: 'French', english_required: false, local_required: false },
  { id: 'DE', iso: 'DE', name_cn: '德国', flag: 'de', primary_language: 'German', english_required: false, local_required: false },
  { id: 'NL', iso: 'NL', name_cn: '荷兰', flag: 'nl', primary_language: 'English', english_required: true, local_required: false },
  { id: 'CH', iso: 'CH', name_cn: '瑞士', flag: 'ch', primary_language: 'English', english_required: true, local_required: false },
  { id: 'IT', iso: 'IT', name_cn: '意大利', flag: 'it', primary_language: 'Italian', english_required: false, local_required: false },
  { id: 'ES', iso: 'ES', name_cn: '西班牙', flag: 'es', primary_language: 'Spanish', english_required: false, local_required: false },
  { id: 'IE', iso: 'IE', name_cn: '爱尔兰', flag: 'ie', primary_language: 'English', english_required: true, local_required: false },
  { id: 'NZ', iso: 'NZ', name_cn: '新西兰', flag: 'nz', primary_language: 'English', english_required: true, local_required: false },
  { id: 'MY', iso: 'MY', name_cn: '马来西亚', flag: 'my', primary_language: 'English', english_required: true, local_required: false },
];

// 学位选项 (当 meta 未加载时使用) — 与后端 stage_map 同步
const FALLBACK_DEGREES_BY_STAGE: Record<string, Array<{degree: string; min_years: number; notes?: string}>> = {
  high_school: [
    { degree: 'Bachelor', min_years: 0, notes: '直申本科 (高考 / 高中毕业)' },
    { degree: 'Foundation', min_years: 0, notes: '预科课程 (1年, 衔接本科大二)' },
    { degree: 'Diploma', min_years: 0, notes: '大一文凭 (1-2年, 国际衔接课程)' },
  ],
  high_school_grad: [
    { degree: 'Bachelor', min_years: 0, notes: '直申本科 (高中毕业)' },
    { degree: 'Foundation', min_years: 0, notes: '预科课程 (1年, 衔接本科大二)' },
    { degree: 'Diploma', min_years: 0, notes: '大一文凭 (1-2年, 国际衔接课程)' },
  ],
  vocational: [
    { degree: 'Bachelor (transfer)', min_years: 0, notes: '转学' },
    { degree: 'Bachelor', min_years: 0, notes: '专科直升本科' },
    { degree: 'Master', min_years: 0, notes: '专升硕' },
  ],
  vocational_grad: [
    { degree: 'Bachelor (transfer)', min_years: 0, notes: '转学' },
    { degree: 'Bachelor', min_years: 0, notes: '专科直升本科' },
    { degree: 'Master', min_years: 0, notes: '专升硕' },
  ],
  undergraduate: [
    { degree: 'Master', min_years: 0, notes: '应届本科可申硕' },
    { degree: 'PhD', min_years: 0, notes: '直博需强科研' },
    { degree: 'Bachelor (transfer)', min_years: 0, notes: '转学' },
  ],
  undergraduate_grad: [
    { degree: 'Master', min_years: 0, notes: '本科毕业可申硕' },
    { degree: 'PhD', min_years: 0, notes: '博士' },
  ],
  graduate_master: [
    { degree: 'PhD', min_years: 0, notes: '硕申博' },
    { degree: 'Master (second)', min_years: 0, notes: '跨专业硕' },
  ],
  graduate_master_grad: [
    { degree: 'PhD', min_years: 0, notes: '申博' },
  ],
  graduate_phd: [
    { degree: 'PhD', min_years: 0, notes: '博士 (本校或外校)' },
    { degree: 'PhD (visiting)', min_years: 0, notes: '访问学者' },
  ],
};

// 计算当前学段到“能申目标学位”还需的年数
function yearsToApplication(currentStage: string, currentStageYear: string): number {
  const stage = currentStage || '';
  const year = currentStageYear || '';

  // 高中在读
  if (stage === 'high_school') {
    if (year === '高三') return 0;
    if (year === '高二') return 1;
    if (year === '高一') return 2;
  }
  if (stage === 'high_school_grad') return 0;

  // 专科在读
  if (stage === 'vocational') {
    if (year === '大三') return 0;
    if (year === '大二') return 1;
    if (year === '大一') return 2;
  }
  if (stage === 'vocational_grad') return 0;

  // 本科在读
  if (stage === 'undergraduate') {
    if (year === '大四' || year === '本科毕业班') return 0;
    if (year === '大三') return 1;
    if (year === '大二') return 2;
    if (year === '大一') return 3;
  }
  if (stage === 'undergraduate_grad') return 0;

  // 硕士在读
  if (stage === 'graduate_master') {
    if (year === '研三' || year === '硕士毕业班') return 0;
    if (year === '研二') return 1;
    if (year === '研一') return 2;
  }
  if (stage === 'graduate_master_grad') return 0;

  // 博士在读
  if (stage === 'graduate_phd') return 0;

  return 0;
}

// 生成 4 个申请季选项 (从最快能申的季开始, Spring+Fall 交替)
function generateIntakeOptions(yearsToGo: number): string[] {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;

  const options: string[] = [];
  let startYear: number;
  let startSeason: 'Spring' | 'Fall';

  if (yearsToGo === 0) {
    // 当年: 如果现在 >= 9月, 当年 Fall 赶不上, 推 currentYear+1 Spring
    if (currentMonth >= 9) {
      startYear = currentYear + 1;
      startSeason = 'Spring';
    } else {
      startYear = currentYear;
      startSeason = 'Fall';
    }
  } else if (yearsToGo === 1) {
    startYear = currentYear + 1;
    startSeason = 'Spring';
  } else {
    startYear = currentYear + 1;
    startSeason = 'Fall';
  }

  let y = startYear;
  let s = startSeason;
  for (let i = 0; i < 4; i++) {
    options.push(`${y} ${s}`);
    if (s === 'Spring') { s = 'Fall'; } else { s = 'Spring'; y++; }
  }

  return options;
}

// 根据 current_stage 推默认意向学位 (后端 meta 未加载时用)
function defaultDegreeForStage(stage: string): string {
  if (stage === 'high_school' || stage === 'high_school_grad' ||
      stage === 'vocational' || stage === 'vocational_grad') {
    return 'Bachelor';
  }
  if (stage === 'undergraduate' || stage === 'undergraduate_grad') {
    return 'Master';
  }
  if (stage === 'graduate_master' || stage === 'graduate_master_grad' ||
      stage === 'graduate_phd') {
    return 'PhD';
  }
  return 'Master';
}


export function MultiStageForm({ onSubmit, loading, initialData, onTrack, onDataChange, suppressInitialOnDataChange }: Props) {
  // Meta
  const [meta, setMeta] = useState<MetaData | null>(null);
  useEffect(() => {
    fetch(`${BFF_BASE_URL}/api/assessment/meta`)
      .then((r) => r.ok ? r.json() : null)
      .then((raw: any) => {
        if (!raw) return setMeta(null);
        // 字段映射：后端 country_id/iso_code/country_name/flag_emoji -> 前端 id/iso/name_cn/flag
        const adapted = {
          ...raw,
          countries: (raw.countries || []).map((c: any) => ({
            id: c.country_id,
            iso: c.iso_code,
            name_cn: c.country_name,
            flag: c.flag_emoji,
            primary_language: c.primary_language,
            english_required: !!c.english_required,
            english_tests: c.accepted_english_tests,
            local_test: c.local_language_test,
            local_required: !!c.local_test_required,
            standardized_tests: c.standardized_tests,
            notes: c.notes,
          })),
        };
        setMeta(adapted);
      })
      .catch(() => {});
  }, []);

  // Form state
  const [step, setStep] = useState(1);
  const [form, setForm] = useState<MultiStageFormData>({
    current_stage: initialData?.current_stage || 'undergraduate',
    current_stage_year: initialData?.current_stage_year || '大三',
    current_school_id: initialData?.current_school_id,
    current_school_name: initialData?.current_school_name,
    current_school_tier: initialData?.current_school_tier,
    current_major: initialData?.current_major || '计算机科学',
    gpa: initialData?.gpa || 3.5,
    gpa_scale: initialData?.gpa_scale || '4.0',
    // R30 (2026-07-17): 留学目标默认项逻辑修复
    //   - 意向国家: 之前默认 ['US'] 是错的 (用户没选), 改为 []
    //   - 意向学位: 之前默认 'Master' (高中生在读情况下是错的), 改为按 current_stage 动态默认
    //   - 意向申请季: 之前固定 '2026 Fall' (高一/大二学生不合适), 改为按 current_stage_year 动态默认
    target_countries: initialData?.target_countries || [],
    target_degree: initialData?.target_degree || '',  // 由 stage_map 动态设置
    target_intake: initialData?.target_intake || '',  // 由 stage+year 动态设置
    target_major: initialData?.target_major || 'Computer Science',
    english_test: initialData?.english_test || 'TOEFL',
    // R-Fix (2026-07-21): 默认 0 — 选「暂无」, 不发起评分硬扣分
    //   (之前默认 100 会被后端误以为是有效 TOEFL 分数)
    english_score: initialData?.english_score ?? 0,
    // R46: 英语小分
    english_sub_reading: initialData?.english_sub_reading ?? 0,
    english_sub_listening: initialData?.english_sub_listening ?? 0,
    english_sub_speaking: initialData?.english_sub_speaking ?? 0,
    english_sub_writing: initialData?.english_sub_writing ?? 0,
    // R47: 接受 path 路径
    accept_pathway: initialData?.accept_pathway ?? true,
    // R48: 课外活动 + 国际交流
    extracurricular: initialData?.extracurricular || [],
    international_exchange: initialData?.international_exchange ?? false,
    international_exchange_top: initialData?.international_exchange_top ?? false,
    local_tests: initialData?.local_tests || {},
    standardized_tests: initialData?.standardized_tests || {},
    research_exp: initialData?.research_exp ?? 1,
    internship_exp: initialData?.internship_exp ?? 1,
    competition: initialData?.competition || [],
    other_competition: initialData?.other_competition || [],
    volunteer: initialData?.volunteer || [],
    summer_camp: initialData?.summer_camp || [],
    student_org: initialData?.student_org || [],
    portfolio: initialData?.portfolio || false,
    publications: initialData?.publications || 0,
    is_cross_disciplinary: initialData?.is_cross_disciplinary ?? false,
    current_major_category: initialData?.current_major_category || "",
    target_major_category: initialData?.target_major_category || "",
    prerequisite_completed: initialData?.prerequisite_completed ?? false,
    has_second_degree: initialData?.has_second_degree ?? false,
    second_degree_field: initialData?.second_degree_field || "",
    lor_status: initialData?.lor_status || '还没开始',  // R32
    work_years: initialData?.work_years ?? 0,  // R45
    contact_status: initialData?.contact_status || 'not_started',  // R45
    // P3.9-4 (2026-07-18): PhD 套磁 + 推荐信
    advisor_contacted: initialData?.advisor_contacted ?? false,
    recommendation_level: initialData?.recommendation_level || undefined,
    budget_min: initialData?.budget_min || 30,
    budget_max: initialData?.budget_max || 70,
    living_min: initialData?.living_min || 12,    // 默认生活费 12 万/年
    living_max: initialData?.living_max || 18,
    scholarship_needed: initialData?.scholarship_needed || false,
    funding_source: initialData?.funding_source || 'parents',
    campus_preference: initialData?.campus_preference || 'urban',
    school_size: initialData?.school_size || 'large',
  });

  const update = <K extends keyof MultiStageFormData>(key: K, val: MultiStageFormData[K]) => {
    setForm((f) => {
      const next = { ...f, [key]: val };
      // R21: 通知 page.tsx 实时更新算法说明
      onDataChange?.(next);
      return next;
    });
  };

  // R21: 初次 mount 也通知一次 (让 page.tsx 一开始就有数据)
  // Bug-fix (2026-07-20): suppressInitialOnDataChange 时跳过 — 重置后不要点亮 R21
  useEffect(() => {
    if (suppressInitialOnDataChange) return;
    onDataChange?.(form);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // R30 (2026-07-17): 当 current_stage 或 current_stage_year 改变时, 自动重置
  //   target_degree (跟 current_stage 联动) 和 target_intake (跟 year 联动)
  //   防止用户高一时还看到默认的 “Master” + “2026 Fall” (逻辑错误)
  //
  // R-Fix (2026-07-21): 同时清空下游字段 — current_school/current_school_id/current_major/gpa/toefl/ielts/research/internship 等。
  //   防止高中跳到本科后, 旧“清华 GPA 3.7”还在 (BUG-008: 切学段不清空下游字段)
  useEffect(() => {
    setForm((prev) => {
      const updates: Partial<MultiStageFormData> = {};

      // 1) target_degree — 如果当前值不在新学段的可申列表里, 重置为第一个
      const eligible =
        (meta?.stage_map && meta.stage_map[prev.current_stage]?.length > 0)
          ? meta.stage_map[prev.current_stage]
          : (FALLBACK_DEGREES_BY_STAGE[prev.current_stage] || []);
      const eligibleCodes = eligible.map((d) => d.degree);
      if (prev.target_degree && !eligibleCodes.includes(prev.target_degree)) {
        updates.target_degree = (eligible[0]?.degree || defaultDegreeForStage(prev.current_stage)) as any;
      } else if (!prev.target_degree) {
        updates.target_degree = (eligible[0]?.degree || defaultDegreeForStage(prev.current_stage)) as any;
      }

      // 2) target_intake — 检查是否在 intakeOptions 里
      const newIntakes = generateIntakeOptions(
        yearsToApplication(prev.current_stage, prev.current_stage_year || '')
      );
      if (prev.target_intake && !newIntakes.includes(prev.target_intake)) {
        updates.target_intake = newIntakes[0] as any;
      } else if (!prev.target_intake) {
        updates.target_intake = newIntakes[0] as any;
      }

      // 3) R-Fix (2026-07-21): 清空跨学段不兼容的字段
      //   current_school_name / current_school_id / current_school_tier / current_major / gpa / english_test / english_score / gre / gmat /
      //   work_experience_years / research_exp / internship_exp / publications
      updates.current_school_name = '';
      updates.current_school_id = '';
      updates.current_school_tier = '';
      updates.current_major = '';
      updates.gpa = 0;
      updates.gpa_scale = '4.0';
      updates.english_test = 'TOEFL';
      updates.english_score = 0;
      // toefl/ielts/gre/gmat scores are inside standardized_tests dict, cleared via english_score
      // updates.jlpt_level = '';  // JLPT not in schema, skip
      updates.work_years = 0;
      updates.research_exp = 0;
      updates.internship_exp = 0;
      updates.publications = 0;
      updates.competition = [];
      updates.other_competition = [];

      if (Object.keys(updates).length === 0) return prev;
      return { ...prev, ...updates };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.current_stage, form.current_stage_year, meta]);

  // 当前步骤能进入下一步
  const canNext = (): boolean => {
    if (step === 1) return !!form.current_stage;
    if (step === 2) {
      // R41 (2026-07-17): 高中阶段也需 GPA - 之前错认为高中无 GPA
      // 高本/本/硕 都需要 major + GPA
      const majorOk = !!form.current_major;
      const gpaOk = (form.gpa || 0) > 0;
      return !!form.current_school_id && majorOk && gpaOk;
    }
    if (step === 3) return form.target_countries.length > 0 && !!form.target_degree;
    if (step === 4) return !!form.english_test;
    if (step === 5) return true;
    if (step === 6) return form.budget_max > form.budget_min;
    return false;
  };

  const next = () => {
    if (canNext() && step < 6) {
      setStep(step + 1);
      onTrack?.('assessment_step_complete', { step });
    }
  };
  const back = () => step > 1 && setStep(step - 1);

  const handleSubmit = async () => {
    onTrack?.('assessment_submit', { step: 6 });
    await onSubmit(form);
  };

  // 联动: 选国家 → 自动给语言考试项
  const selectedCountries = (meta?.countries || []).filter((c) =>
    form.target_countries.includes(c.id)
  );
  // 联动: 学段 → 可申学位 (优先 meta, fallback 使用内置映射)
  const eligibleDegrees =
    (meta?.stage_map && meta.stage_map[form.current_stage]?.length > 0)
      ? meta.stage_map[form.current_stage]
      : (FALLBACK_DEGREES_BY_STAGE[form.current_stage] || []);

  // R30: 动态生成申请季选项 (根据 current_stage + current_stage_year 算出需要等几年)
  const intakeOptions = generateIntakeOptions(
    yearsToApplication(form.current_stage, form.current_stage_year || '')
  );

  return (
    <Card padding="lg" className="lg:sticky lg:top-20 lg:self-start mb-20 md:mb-0">
      {/* 进度条 */}
      <StepProgress currentStep={step} onJump={(s) => s < step && setStep(s)} />

      {/* 当前步骤内容 */}
      <div className="mt-5">
        {step === 1 && (
          <Step1Stage form={form} update={update} />
        )}
        {step === 2 && (
          <Step2School form={form} update={update} meta={meta} />
        )}
        {step === 3 && (
          <Step3Target
            form={form}
            update={update}
            meta={meta}
            eligibleDegrees={eligibleDegrees}
            intakeOptions={intakeOptions}
          />
        )}
        {step === 4 && (
          <Step4Language
            form={form}
            update={update}
            selectedCountries={selectedCountries}
          />
        )}
        {step === 5 && (
          <Step5SoftBackground form={form} update={update} />
        )}
        {step === 6 && (
          <Step6Budget
            form={form}
            update={update}
            selectedCountries={selectedCountries}
          />
        )}
      </div>

      {/* 导航 — R-Design 2026-09-16: 更大更醒目
          问题: 移动端按钮 px-4 py-2 偏小, 白底跟 Card 融为一体, 用户"看不清下一步"
          修法:
            1. 按钮加大到 px-6 py-3, 字号 text-base, 加 shadow-glow-primary
            2. 渐变主色 from-primary-500 to-primary-600, hover 上浮
            3. 移动端固定底栏用更强的顶部分隔 (border + shadow + bg-white 不透)
            4. 「上一步」改 btn-ghost 但保留可点区域, 不至于隐形
      */}
      <div className="fixed bottom-0 left-0 right-0 z-50 -mx-6 -mb-6 mt-6 px-5 py-4 border-t-2 border-primary-100 bg-white shadow-[0_-8px_24px_rgba(15,23,42,0.12)] md:static md:mx-0 md:mb-0 md:px-0 md:py-0 md:mt-8 md:pt-6 md:border-t md:border-gray-100 md:relative md:z-auto md:shadow-none md:bg-transparent rounded-b-2xl"
           style={{ paddingBottom: 'max(1rem, env(safe-area-inset-bottom))' }}>
        <div className="flex items-center justify-between gap-3">
          <button
            onClick={back}
            disabled={step === 1}
            className="btn-ghost disabled:opacity-30"
          >
            <ChevronLeft className="w-4 h-4" />
            上一步
          </button>

          {/* 移动端当前步指示 (桌面端顶部进度条已够) */}
          <span className="text-xs font-medium text-gray-400 md:hidden">
            第 {step} / 6 步
          </span>

          {step < 6 ? (
            <button
              onClick={next}
              disabled={!canNext()}
              className="btn-primary px-6 py-3 text-base"
            >
              下一步
              <ChevronRight className="w-5 h-5" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="inline-flex items-center justify-center gap-2 px-6 py-3 text-base rounded-xl font-semibold text-white
                         bg-gradient-to-br from-emerald-500 to-emerald-600
                         shadow-[0_4px_20px_rgba(16,185,129,0.32)]
                         hover:from-emerald-600 hover:to-emerald-700 hover:shadow-lift hover:-translate-y-0.5
                         active:translate-y-0 transition-all duration-200
                         disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  评估中…
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  开始评估
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </Card>
  );
}

// ─── Step Progress ─────────────────────────────────────────────────
function StepProgress({ currentStep, onJump }: { currentStep: number; onJump: (s: number) => void }) {
  return (
    <div>
      {/* R-Design 2026-09-16: 进度圆点更醒目
          - current: 大一号 + glow 阴影 + ring 聚焦
          - past: 翠绿 + hover scale
          - 连线: 每两段之间画 4px 渐变线 (用 absolute 布局, 替代 hidden)
          - 底部进度条: 加粗到 h-1.5, 颜色用 primary→emerald 渐变, 跟圆点呼应
      */}
      <div className="relative flex items-start justify-between gap-0.5 mb-4 px-1">
        {/* 底部连线 (跨整个进度条) */}
        <div aria-hidden className="absolute top-[18px] left-6 right-6 h-0.5 bg-gray-200 rounded-full -z-0" />
        <div
          aria-hidden
          className="absolute top-[18px] left-6 h-0.5 bg-gradient-to-r from-emerald-400 to-primary-400 rounded-full transition-all duration-500 -z-0"
          style={{ width: `calc(${(Math.min(currentStep - 1, 5) / 5) * 100}% - 0px)` }}
        />
        {STEPS.map((s, i) => {
          const Icon = s.icon;
          const isCurrent = currentStep === s.id;
          const isPast = currentStep > s.id;
          return (
            <div
              key={s.id}
              className="flex-1 flex flex-col items-center gap-1.5 relative z-10"
            >
              <button
                onClick={() => onJump(s.id)}
                disabled={!isPast && !isCurrent}
                className={`rounded-full flex items-center justify-center transition-all duration-200 ${
                  isCurrent
                    ? 'w-11 h-11 bg-gradient-to-br from-primary-500 to-primary-600 text-white shadow-glow-primary ring-4 ring-primary-100 scale-105'
                    : isPast
                    ? 'w-9 h-9 bg-emerald-500 text-white cursor-pointer hover:scale-110 shadow-md'
                    : 'w-9 h-9 bg-white border-2 border-gray-200 text-gray-400 cursor-not-allowed'
                }`}
                title={s.name}
              >
                {isPast ? <CheckCircle2 className="w-5 h-5" /> : <Icon className={isCurrent ? 'w-5 h-5' : 'w-4 h-4'} strokeWidth={isCurrent ? 2 : 1.75} />}
              </button>
              <div className={`text-[11px] text-center leading-tight font-medium transition-colors ${
                isCurrent ? 'text-primary-700' : isPast ? 'text-emerald-700' : 'text-gray-400'
              }`}>
                {s.name}
              </div>
            </div>
          );
        })}
      </div>
      {/* 进度条 (桌面 / 移动一致) */}
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden shadow-inner">
        <div
          className="h-full bg-gradient-to-r from-primary-500 via-primary-400 to-emerald-500 transition-all duration-500 rounded-full"
          style={{ width: `${(currentStep / 6) * 100}%` }}
        />
      </div>
      {/* 当前步描述 (移动端用户容易迷失, 加一行说明) */}
      <p className="mt-3 text-center text-sm text-gray-500">
        <span className="font-semibold text-primary-700">第 {currentStep} 步</span>
        <span className="mx-1.5 text-gray-300">·</span>
        {STEPS[currentStep - 1].desc}
      </p>
    </div>
  );
}

// ─── Step 1: 当前学段 ─────────────────────────────────────────────
function Step1Stage({ form, update }: { form: MultiStageFormData; update: <K extends keyof MultiStageFormData>(k: K, v: MultiStageFormData[K]) => void }) {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-bold text-gray-800 inline-flex items-center gap-2">
        <GraduationCap className="w-5 h-5 text-primary-600" />
        你现在的学段?
      </h3>

      {/* R22a (2026-07-16): 5 大类按钮 + 选大类后下面显示子状态 */}
      <div className="grid grid-cols-3 gap-2">
        {Object.entries(STAGE_GROUP_LABELS).map(([group, label]) => (
          <button
            key={group}
            onClick={() => {
              // 选大类后默认选第一个子状态 (如本科 → 大一)
              const subs = STAGE_SUBSTATES[group as StageGroup];
              const defaultSub = subs[0];
              update('current_stage', defaultSub.code as any);
              update('current_stage_year', defaultSub.label);
            }}
            className={`px-3 py-3 rounded-lg border text-sm transition ${
              STAGE_TO_GROUP[form.current_stage] === group
                ? 'border-primary-500 bg-primary-50 text-primary-700 font-medium'
                : 'border-gray-200 hover:border-gray-300 text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* 子状态 (显示当前大类的所有子状态) */}
      {form.current_stage && (
        <Field label="具体年级 / 状态">
          <div className="grid grid-cols-3 gap-1.5">
            {(STAGE_SUBSTATES[STAGE_TO_GROUP[form.current_stage] as StageGroup] || []).map((sub) => {
              // R22 (2026-07-17): 多个 sub 共用同一 code (例如 高一/二/三 都 code='high_school'),
              // 必须同时匹配 current_stage_year 才能唯一定位当前选中项,
              // 否则所有 code 相同的 sub 会同时高亮且无法取消。
              const active = form.current_stage === sub.code && form.current_stage_year === sub.label;
              return (
                <button
                  key={sub.label}
                  onClick={() => {
                    update('current_stage', sub.code as any);
                    update('current_stage_year', sub.label);
                  }}
                  className={`px-2 py-1.5 text-xs rounded border transition ${
                    active
                      ? 'border-primary-500 bg-primary-100 text-primary-700 font-medium'
                      : 'border-gray-200 hover:border-gray-300 text-gray-700'
                  }`}
                >
                  {sub.label}
                </button>
              );
            })}
          </div>
        </Field>
      )}
    </div>
  );
}

// ─── Step 2: 院校 ────────────────────────────────────────────
function Step2School({ form, update, meta }: { form: MultiStageFormData; update: <K extends keyof MultiStageFormData>(k: K, v: MultiStageFormData[K]) => void; meta: MetaData | null }) {
  // 根据学段给 SchoolPicker eduLevel (R18 严谨分类)
  const eduLevel =
    (form.current_stage === 'high_school' || form.current_stage === 'high_school_grad') ? 'high_school' :
    (form.current_stage === 'vocational' || form.current_stage === 'vocational_grad') ? 'vocational_college' :
    'university';  // 本/硕/博/已毕业都按 university 过滤

  return (
    <div className="space-y-4">
      <h3 className="text-base font-bold text-gray-800 inline-flex items-center gap-2">
        <School className="w-5 h-5 text-primary-600" />
        你的院校
      </h3>

      <Field label="院校 (自动判定 tier)">
        <SchoolPicker
          value={form.current_school_name || ''}
          schoolId={form.current_school_id}
          eduLevel={eduLevel}
          onChange={(name) => update('current_school_name', name)}
          onIdChange={(id) => update('current_school_id', id)}
          onDetailChange={(d: any) => {
            // SchoolPicker 返回 detail 时自动存 tier
            if (d) {
              const tier =
                d.cn_category_code === '985' ? '985' :
                d.cn_category_code === '211' ? '211' :
                d.cn_category_code === 'double_first_class_a' ? '985' :
                d.country && d.country !== 'CN' ? '海外' :
                '双非';
              update('current_school_tier', tier);
            }
          }}
        />
      </Field>

      {form.current_school_tier && (
        <div className="text-xs text-emerald-700 bg-emerald-50 px-3 py-2 rounded-lg">
          ✅ 自动判定 tier: <strong>{form.current_school_tier}</strong>
          {form.current_school_tier === '985' && ' (权重最高, 申请优势大)'}
          {form.current_school_tier === '211' && ' (良好)'}
          {form.current_school_tier === '双非' && ' (需重点突出软背景)'}
          {form.current_school_tier === '海外' && ' (英文授课优势)'}
        </div>
      )}

      {/* R18 (2026-07-16): 高中生不需要选专业 (还没分专业) */}
      {!(form.current_stage === 'high_school' || form.current_stage === 'high_school_grad') && (
        <Field label="当前专业">
          <MajorPicker
            value={form.current_major || ''}
            onChange={(name) => update('current_major', name)}
            placeholder="搜索或选择你的专业 (如: 计算机科学)"
          />
        </Field>
      )}

      {/* R41 (2026-07-17): 高中阶段也需要 GPA - 美国本科看高中成绩
          之前 R18 认为高中生无 GPA 错: 高中平时成绩/校排位对美国本科申请极重要
          不同学段提示不同: 高中 (不取 GPA 4.0 制, 用 4.0+ 或 5.0 或百分制) vs 本科 (4.0 制) */}
      <div className="grid grid-cols-2 gap-2">
        <Field label={form.current_stage.startsWith('high_school') || form.current_stage.startsWith('vocational') ? '高中/中职 GPA' : 'GPA'}>
          <input
            type="number"
            step="0.01"
            min="0"
            max={form.gpa_scale === '100' ? '100' : (form.current_stage.startsWith('high_school') || form.current_stage.startsWith('vocational')) ? '5' : '4'}
            value={form.gpa || ''}
            onChange={(e) => {
              // T1-X (2026-07-25 BUG-009 fix): 前端 GPA 范围校验 + 错误提示
              // 历史: GPA 允许 -1, 999, "" 全部 accept
              // 根因: min="0" 但 input 是 number type, 负数没拦 (e.g. -1), max 只看 gpa_scale 不看实际值
              // 修: onChange 校验数值范围 (0-4.3 4.0制, 0-5 5.0制, 0-100 百分制)
              // + 超过范围 clamp 到最近有效值 + inline 错误提示
              const raw = e.target.value;
              const num = parseFloat(raw);
              if (raw === '' || isNaN(num)) {
                update('gpa', 0);
                return;
              }
              const max = form.gpa_scale === '100' ? 100 :
                         (form.current_stage.startsWith('high_school') || form.current_stage.startsWith('vocational')) ? 5 : 4;
              if (num < 0) {
                update('gpa', 0);
                e.target.value = '0';
                return;
              }
              if (num > max) {
                update('gpa', max);
                e.target.value = String(max);
                return;
              }
              update('gpa', num);
            }}
            placeholder={
              form.current_stage.startsWith('high_school') || form.current_stage.startsWith('vocational')
                ? '高中 GPA (例 3.8/4.0 或 90/100)'
                : form.current_stage === 'undergraduate_grad' ? '本科 GPA (例 3.5)' : '请输入 GPA'
            }
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
          />
        </Field>
        <Field label="GPA 制">
          <select
            value={form.gpa_scale || '4.0'}
            onChange={(e) => update('gpa_scale', e.target.value)}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
          >
            <option value="4.0">4.0 制</option>
            <option value="4.3">4.3 制</option>
            <option value="5.0">5.0 制</option>
            <option value="100">百分制</option>
          </select>
        </Field>
      </div>
    </div>
  );
}

// ─── Step 3: 留学目标 ────────────────────────────────────────────
function Step3Target({ form, update, meta, eligibleDegrees, intakeOptions }: {
  form: MultiStageFormData;
  update: <K extends keyof MultiStageFormData>(k: K, v: MultiStageFormData[K]) => void;
  meta: MetaData | null;
  eligibleDegrees: Array<{ degree: string; min_years: number; notes?: string }>;
  intakeOptions: string[];
}) {
  // R31 (2026-07-17): 优先用 meta, fallback 17 国家, 避免 grid 空白
  const countries = meta?.countries?.length ? meta.countries : FALLBACK_COUNTRIES;
  const toggleCountry = (id: string) => {
    const arr = form.target_countries.includes(id)
      ? form.target_countries.filter((c) => c !== id)
      : [...form.target_countries, id].slice(0, 5);
    update('target_countries', arr);
  };

  return (
    <div className="space-y-4">
      <h3 className="text-base font-bold text-gray-800 inline-flex items-center gap-2">
        <MapPin className="w-5 h-5 text-primary-600" />
        留学目标
      </h3>

      <Field label={`意向国家 (多选, 已选 ${form.target_countries.length}/5)`}>
        <div className="space-y-2">
          {/* R31 (2026-07-17): 提示 + 快捷 + 清晰可见的 country grid, 不限高 */}
          <div className="flex items-center justify-between gap-2 text-xs text-gray-500">
            <span>点击下方国家/地区标签选择 (最多5个)</span>
            {form.target_countries.length > 0 && (
              <button
                type="button"
                onClick={() => update('target_countries', [])}
                className="text-primary-600 hover:text-primary-800 hover:underline"
              >
                清空
              </button>
            )}
          </div>
          {countries.length === 0 ? (
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="h-9 bg-gray-100 rounded animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
              {countries.map((c) => {
                const selected = form.target_countries.includes(c.id);
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => toggleCountry(c.id)}
                    className={`px-2 py-2 text-xs rounded border transition flex items-center gap-1 ${
                      selected
                        ? 'border-primary-500 bg-primary-50 text-primary-700 font-medium ring-1 ring-primary-500'
                        : 'border-gray-200 hover:border-gray-300 text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <span className="text-base">{c.flag}</span>
                    <span>{c.name_cn}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </Field>

      <Field label={`意向学位 (${STAGE_LABELS[form.current_stage]} 可申)`}>
        <select
          value={form.target_degree}
          onChange={(e) => update('target_degree', e.target.value)}
          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
        >
          {eligibleDegrees.length === 0 ? (
            <option value={form.target_degree}>{form.target_degree || '请选择学位'}</option>
          ) : (
            eligibleDegrees.map((d) => (
              <option key={d.degree} value={d.degree}>
                {d.degree} {d.notes && `(${d.notes})`}
              </option>
            ))
          )}
        </select>
        {/* R40 (2026-07-17): 路径选择指南 - 解释 3 种学位的区别 */}
        <div className="mt-2 p-2.5 bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-100 rounded-lg text-xs text-gray-700 space-y-1">
          <div className="font-semibold text-indigo-800">🌍 3 种路径怎么选？</div>
          <div><span className="font-semibold">Bachelor</span> = 高考生直申本科 (如美国综排 Top100)</div>
          <div><span className="font-semibold">Foundation</span> = 1年预科课程 → 衔接本科大二 (高考不理想/语言未达标)</div>
          <div><span className="font-semibold">Diploma</span> = 1-2年文凭课程 (澳洲/英国/新加坡常见, 含金量≈大一/大二)</div>
        </div>
      </Field>

      <Field label="意向申请季">
        <div className="grid grid-cols-2 gap-2">
          {intakeOptions.map((s) => (
            <button
              key={s}
              onClick={() => update('target_intake', s)}
              className={`px-3 py-2 text-xs rounded border ${
                form.target_intake === s
                  ? 'border-primary-500 bg-primary-50 text-primary-700 font-medium'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </Field>

      <Field label="意向专业">
        <MajorPicker
          value={form.target_major || ''}
          onChange={(name) => update('target_major', name)}
          placeholder="如: Computer Science"
        />
      </Field>

      {/* R47 (R42 P1-1): 是否接受 path 路径 (高中阶段尤其重要) */}
      {(['high_school', 'high_school_grad'].includes(form.current_stage) ||
        ['Foundation', 'Diploma'].includes(form.target_degree || '')) && (
        <Field label="是否接受路径课程 (Pathway)">
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.accept_pathway ?? true}
              onChange={(e) => update('accept_pathway', e.target.checked)}
              className="w-4 h-4 mt-1 accent-primary-600"
            />
            <div>
              <div className="font-medium">愿意读预科/衔接课程 (Foundation/Diploma)</div>
              <div className="text-xs text-gray-500 mt-0.5">
                如雅思未达标 / 高中成绩单不够, 可读 1 年预科再升本科大二. 澳洲/英国/新加坡常见.
              </div>
            </div>
          </label>
        </Field>
      )}
    </div>
  );
}

// ─── Step 4: 语言 + 标化 ────────────────────────────────────────
function Step4Language({ form, update, selectedCountries }: {
  form: MultiStageFormData;
  update: <K extends keyof MultiStageFormData>(k: K, v: MultiStageFormData[K]) => void;
  selectedCountries: CountryMeta[];
}) {
  const needEnglish = selectedCountries.some((c) => c.english_required);

  // R32 (2026-07-17): 根据 current_stage + target_degree 智能选考试
  // - 高中 申 Bachelor: TOEFL/IELTS + SAT/ACT (主) + 小语种
  // - 本科/专科 申 Master: TOEFL/IELTS + GRE (主) / GMAT (商科)
  // - 硕 申 PhD: TOEFL/IELTS + GRE (主)
  const stage = form.current_stage;
  const deg = form.target_degree || '';
  const showSAT = stage === 'high_school' || stage === 'high_school_grad' ||
                  (stage === 'vocational' && deg === 'Bachelor');
  const showGRE = (stage === 'undergraduate' || stage === 'undergraduate_grad' ||
                   stage === 'graduate_master' || stage === 'graduate_master_grad') &&
                  (deg === 'Master' || deg === 'PhD');
  const showGMAT = showGRE && (deg === 'Master');  // GMAT 主要是商科 master
  const showLSAT = stage === 'undergraduate' && deg.includes('Bachelor');  // 本科申 JD (法学)
  const showMCAT = stage === 'undergraduate' && deg.includes('Bachelor');  // 本科申医学院

  // 选考提示
  const examHints: string[] = [];
  if (showSAT) examHints.push('SAT/ACT: 本科申请重要, Top30 要 1500+');
  if (showGRE) examHints.push('GRE: 硕博申请重要, Top30 要 320+');
  if (showGMAT) examHints.push('GMAT: 商科/MBA 重要, Top30 要 720+');

  return (
    <div className="space-y-4">
      <h3 className="text-base font-bold text-gray-800 inline-flex items-center gap-2">
        <Languages className="w-5 h-5 text-primary-600" />
        语言 + 标化成绩
      </h3>

      {/* R32 智能提示: 根据学段×学位告诉用户该填什么 */}
      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs">
        <div className="font-semibold text-blue-800 mb-1">📋 你选的国家:</div>
        <ul className="space-y-0.5 text-blue-700 mb-2">
          {selectedCountries.map((c) => (
            <li key={c.id}>
              {c.flag} {c.name_cn} - 主语言 {c.primary_language}
              {c.english_required && ' (需英语)'}
              {c.local_required && ` (需 ${c.local_test})`}
            </li>
          ))}
        </ul>
        {examHints.length > 0 && (
          <div className="mt-2 pt-2 border-t border-blue-200">
            <div className="font-semibold text-blue-800 mb-1">🎯 {STAGE_LABELS[stage]} + {deg} 推荐考:</div>
            <ul className="space-y-0.5 text-blue-700">
              {examHints.map((h, i) => <li key={i}>• {h}</li>)}
            </ul>
          </div>
        )}
      </div>

      {needEnglish && (
        <>
          <div className="grid grid-cols-3 gap-2">
            <Field label="英语考试">
              <select
                value={form.english_test || 'TOEFL'}
                onChange={(e) => update('english_test', e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
              >
                <option>TOEFL</option>
                <option>IELTS</option>
                <option>PTE</option>
                <option>Duolingo</option>
                <option>CAE</option>
                <option>暂无</option>
              </select>
            </Field>
            <Field label="分数">
              <input
                type="number"
                value={form.english_score || 0}
                onChange={(e) => update('english_score', parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
              />
            </Field>
            <Field label="满分">
              <div className="px-3 py-2 text-sm text-gray-500">
                {form.english_test === 'TOEFL' ? '/ 120' :
                 form.english_test === 'IELTS' ? '/ 9.0' :
                 form.english_test === 'PTE' ? '/ 90' :
                 form.english_test === 'Duolingo' ? '/ 160' : '—'}
              </div>
            </Field>
          </div>

          {/* R46 (R42 P0-4): 英语小分 (G5 要求单项 ≥ 6.5/7.0) */}
          <div className="p-2 bg-yellow-50 border border-yellow-100 rounded text-xs text-yellow-800">
            ⚠️ G5 (牛剑/LSE/ICL) 要求小分: 雅思 ≥ 6.5 (单项), 托福 ≥ 22 (口语/写作)
          </div>
          <div className="text-xs font-semibold text-gray-700 mt-1">英语小分 ({form.english_test || 'TOEFL'})</div>
          <div className="grid grid-cols-4 gap-2">
            <Field label="阅读">
              <input
                type="number" step={form.english_test === 'IELTS' ? '0.5' : '1'} min="0"
                max={form.english_test === 'IELTS' ? '9' : '30'}
                value={form.english_sub_reading || ''}
                onChange={(e) => update('english_sub_reading', parseFloat(e.target.value) || 0)}
                placeholder={form.english_test === 'TOEFL' ? '例 26' : '例 7.5'}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
              />
            </Field>
            <Field label="听力">
              <input
                type="number" step={form.english_test === 'IELTS' ? '0.5' : '1'} min="0"
                max={form.english_test === 'IELTS' ? '9' : '30'}
                value={form.english_sub_listening || ''}
                onChange={(e) => update('english_sub_listening', parseFloat(e.target.value) || 0)}
                placeholder={form.english_test === 'TOEFL' ? '例 25' : '例 7.5'}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
              />
            </Field>
            <Field label="口语">
              <input
                type="number" step={form.english_test === 'IELTS' ? '0.5' : '1'} min="0"
                max={form.english_test === 'IELTS' ? '9' : '30'}
                value={form.english_sub_speaking || ''}
                onChange={(e) => update('english_sub_speaking', parseFloat(e.target.value) || 0)}
                placeholder={form.english_test === 'TOEFL' ? '例 22' : '例 6.5'}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
              />
            </Field>
            <Field label="写作">
              <input
                type="number" step={form.english_test === 'IELTS' ? '0.5' : '1'} min="0"
                max={form.english_test === 'IELTS' ? '9' : '30'}
                value={form.english_sub_writing || ''}
                onChange={(e) => update('english_sub_writing', parseFloat(e.target.value) || 0)}
                placeholder={form.english_test === 'TOEFL' ? '例 24' : '例 6.5'}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
              />
            </Field>
          </div>
        </>
      )}

      {/* 小语种考试 (按国家) */}
      {selectedCountries.filter((c) => c.local_required).map((c) => (
        <Field key={c.id} label={`${c.flag} ${c.name_cn} - ${c.local_test}`}>
          <select
            value={form.local_tests?.[c.id] || ''}
            onChange={(e) => update('local_tests', { ...form.local_tests, [c.id]: e.target.value })}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
          >
            <option value="">暂无</option>
            {c.id === 'JP' && <><option>JLPT N1</option><option>JLPT N2</option></>}
            {c.id === 'KR' && <><option>TOPIK 6</option><option>TOPIK 5</option><option>TOPIK 4</option><option>TOPIK 3</option></>}
            {c.id === 'FR' && <><option>DELF B2</option><option>DELF C1</option><option>TCF B2</option><option>TCF C1</option></>}
            {c.id === 'DE' && <><option>TestDaF 4</option><option>TestDaF 5</option><option>DSH 2</option><option>DSH 3</option></>}
            {c.id === 'IT' && <><option>CILS B1</option><option>CILS B2</option><option>CILS C1</option></>}
            {c.id === 'ES' && <><option>DELE B2</option><option>DELE C1</option><option>SIELE B2</option></>}
          </select>
        </Field>
      ))}

      {/* SAT/ACT (高中生申本要) */}
      {showSAT && (
        <>
          <Field label="SAT (美国本科要, Top30 要 1500+)">
            <input
              type="number"
              min="400"
              max="1600"
              value={form.standardized_tests?.SAT || ''}
              onChange={(e) => update('standardized_tests', { ...form.standardized_tests, SAT: parseInt(e.target.value) || 0 })}
              placeholder="例如: 1500 (EBRW 700 + Math 800)"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
            />
          </Field>
          <Field label="ACT (SAT 替代, 美国本科要)">
            <input
              type="number"
              min="1"
              max="36"
              value={form.standardized_tests?.ACT || ''}
              onChange={(e) => update('standardized_tests', { ...form.standardized_tests, ACT: parseInt(e.target.value) || 0 })}
              placeholder="例如: 33 (Top30 需 33+)"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
            />
          </Field>
          <Field label="AP (美本申请含金量高, 有 ≥4 门 5 分为佳)">
            <div className="grid grid-cols-3 gap-2">
              {[
                { v: 1, l: '1 门' },
                { v: 2, l: '2 门' },
                { v: 3, l: '3 门' },
                { v: 4, l: '4 门' },
                { v: 5, l: '5 门' },
                { v: 6, l: '6+ 门' },
                { v: 7, l: '7+ 门' },
                { v: 8, l: '8+ 门' },
                { v: 0, l: '暂无' },
              ].map((o) => (
                <button
                  key={o.v}
                  type="button"
                  onClick={() => update('standardized_tests', { ...form.standardized_tests, AP_count: o.v })}
                  className={`px-2 py-1.5 text-xs rounded border transition ${
                    form.standardized_tests?.AP_count === o.v
                      ? 'border-primary-500 bg-primary-50 text-primary-700'
                      : 'border-gray-200 hover:border-gray-300 text-gray-700'
                  }`}
                >
                  {o.l}
                </button>
              ))}
            </div>
          </Field>
        </>
      )}

      {/* GRE (硕博要) */}
      {showGRE && (
        <Field label="GRE (硕博申请, Top30 要 320+)">
          <input
            type="number"
            min="260"
            max="340"
            value={form.standardized_tests?.GRE || ''}
            onChange={(e) => update('standardized_tests', { ...form.standardized_tests, GRE: parseInt(e.target.value) || 0 })}
            placeholder="例如: 320 (Verbal 160 + Quant 160)"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
          />
        </Field>
      )}

      {/* GMAT (商科 Master 要) */}
      {showGMAT && (
        <Field label="GMAT (商科/MBA, Top30 要 720+)">
          <input
            type="number"
            min="200"
            max="800"
            value={form.standardized_tests?.GMAT || ''}
            onChange={(e) => update('standardized_tests', { ...form.standardized_tests, GMAT: parseInt(e.target.value) || 0 })}
            placeholder="例如: 720"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
          />
        </Field>
      )}

      {/* LSAT (法本要) */}
      {showLSAT && (
        <Field label="LSAT (美本 JD 法学要, Top14 要 170+)">
          <input
            type="number"
            min="120"
            max="180"
            value={form.standardized_tests?.LSAT || ''}
            onChange={(e) => update('standardized_tests', { ...form.standardized_tests, LSAT: parseInt(e.target.value) || 0 })}
            placeholder="例如: 170"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
          />
        </Field>
      )}

      {/* MCAT (美本医学院要) */}
      {showMCAT && (
        <Field label="MCAT (美本医学院要, Top10 要 518+)">
          <input
            type="number"
            min="472"
            max="528"
            value={form.standardized_tests?.MCAT || ''}
            onChange={(e) => update('standardized_tests', { ...form.standardized_tests, MCAT: parseInt(e.target.value) || 0 })}
            placeholder="例如: 518"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
          />
        </Field>
      )}
    </div>
  );
}

// ─── Step 5: 软背景 ────────────────────────────────────────────
// R32 (2026-07-17): 软背景按 学段×学位 智能显示字段
// 设计原则:
// - 高中生无科研/论文/实习/工作, 不应该出现这些字段 (避免 0 = 0 = 0 充数感)
// - 不同学段的"高质量背景"不同: 高中生看奥赛/夏令营, 本科生看实习/论文, 硕看科研
// - 作品集仅艺术/设计类要 (其他专业选不选无所谓)
// - 竞赛分学科竞赛 (高中生含金量高) vs 商赛/挑战杯 (本科生含金量高)

function getStageGroup(currentStage: string): 'high_school' | 'vocational' | 'undergraduate' | 'graduate' {
  if (currentStage === 'high_school' || currentStage === 'high_school_grad') return 'high_school';
  if (currentStage === 'vocational' || currentStage === 'vocational_grad') return 'vocational';
  if (currentStage === 'undergraduate' || currentStage === 'undergraduate_grad') return 'undergraduate';
  return 'graduate';
}

function Step5SoftBackground({ form, update }: { form: MultiStageFormData; update: <K extends keyof MultiStageFormData>(k: K, v: MultiStageFormData[K]) => void }) {
  // R35 (2026-07-17): 选 "无" 互斥 - 选 “无” → 清空其他, 选其他 → 删掉 “无”
  // 避免多选里 “无” 跟其他项互冲 (RK 反馈)
  //
  // R-Fix (2026-07-21): 「学科竞赛」和「其他竞赛」看似是同一个字段 competition,
  // 但 UI 是两个分开的 Fields (一个是奥赛, 一个是商赛). 之前两 Field 共用
  // form.competition 导致「无」联动互清理 (RK 反馈). 修复: 两 Field 各管各 array,
  // toggle 的 key 可以是 'competition' 或 'other_competition'.
  const toggle = <K extends 'competition' | 'other_competition' | 'volunteer' | 'summer_camp' | 'student_org'>(key: K, val: string) => {
    const arr = (form[key] as string[]) || [];
    let next: string[];
    if (val === '无') {
      // 选 "无": 只保留 "无" (如果已有则取消, 否则只保留 “无”)
      next = arr.includes('无') ? [] : ['无'];
    } else {
      // 选其他项: 从数组移除该值 (如果已有) 或加入 (如果没有), 同时清掉 "无"
      next = arr.includes(val)
        ? arr.filter((v) => v !== val)
        : [...arr.filter((v) => v !== '无'), val];
    }
    update(key, next as MultiStageFormData[K]);
  };

  const stageGroup = getStageGroup(form.current_stage);

  // 不同学段 + 目标学位 → 可见的字段
  const visibility = {
    show_research: stageGroup === 'undergraduate' || stageGroup === 'graduate',
    show_internship: stageGroup !== 'high_school',  // 高中生无实习
    show_publications: stageGroup === 'undergraduate' || stageGroup === 'graduate',
    show_competition: true,  // 都有
    show_volunteer: true,
    show_portfolio: true,
    show_olympiad: stageGroup === 'high_school' || stageGroup === 'undergraduate',  // 高中含金量 + 本科少量
    show_summer_camp: stageGroup === 'high_school',  // 高中生独有 (顶尖夏校含金量极高)
    show_leadership: true,  // 都有
    show_work_exp: stageGroup !== 'high_school',
    show_lor: stageGroup === 'undergraduate' || stageGroup === 'graduate',  // 硕博要推荐信
    show_cross_disc: true,  // 跨专业字段 (硕博 + 本科都有)
    // R45: MBA 申请要求 work_years >= 2, PhD 申请 0 工作
    show_work_years: form.target_degree === 'MBA' || stageGroup === 'graduate',
    // R45: PhD 必填套磁状态 (硕申博极重要)
    show_contact: form.target_degree === 'PhD' || stageGroup === 'graduate' && (form.target_degree === 'PhD' || form.target_degree === 'Master'),
  };

  return (
    <div className="space-y-4">
      <h3 className="text-base font-bold text-gray-800 inline-flex items-center gap-2">
        <Sparkles className="w-5 h-5 text-primary-600" />
        软背景
      </h3>

      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-800">
        💡 {STAGE_LABELS[form.current_stage]} + {form.target_degree || '?'} →
        你的“高质量背景”是：
        {stageGroup === 'high_school' && ' 竞赛名次 + 顶尖夏校 + 学科奥赛 + 社团领导力'}
        {stageGroup === 'vocational' && ' 实习经历 + 技能证书 + 学业表现'}
        {stageGroup === 'undergraduate' && ' 科研 + 论文 + 实习 + 竞赛 + 推荐信'}
        {stageGroup === 'graduate' && ' 科研论文 + 会议 + 推荐人关系 + 研究方向匹配'}
      </div>

      {/* 科研 + 实习 (硕博 + 本科) */}
      {(visibility.show_research || visibility.show_internship) && (
        <div className="grid grid-cols-2 gap-2">
          {visibility.show_research && (
            <Field label="科研段数">
              <input
                type="number"
                min="0"
                value={form.research_exp}
                onChange={(e) => update('research_exp', parseInt(e.target.value) || 0)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
              />
            </Field>
          )}
          {visibility.show_internship && (
            <Field label={visibility.show_work_exp ? '实习/工作段数' : '实习段数'}>
              <input
                type="number"
                min="0"
                value={form.internship_exp}
                onChange={(e) => update('internship_exp', parseInt(e.target.value) || 0)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
              />
            </Field>
          )}
        </div>
      )}

      {/* 论文 / 专利 (硕博 + 本科申硕) */}
      {visibility.show_publications && (
        <Field label="发表论文 / 专利">
          <input
            type="number"
            min="0"
            value={form.publications || 0}
            onChange={(e) => update('publications', parseInt(e.target.value) || 0)}
            placeholder="0 = 无, 1+ = 有发表"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
          />
        </Field>
      )}

      {/* P3.9-4 (2026-07-18): PhD 套磁状态 */}
      {visibility.show_contact && (
        <Field label="📧 是否联系过导师 (PhD 关键)">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => update('advisor_contacted', true)}
              className={`flex-1 px-3 py-2 text-sm rounded-lg border transition ${
                form.advisor_contacted
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-200 hover:border-gray-300 text-gray-700'
              }`}
            >
              ✅ 已联系 (或面试过)
            </button>
            <button
              type="button"
              onClick={() => update('advisor_contacted', false)}
              className={`flex-1 px-3 py-2 text-sm rounded-lg border transition ${
                !form.advisor_contacted
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-200 hover:border-gray-300 text-gray-700'
              }`}
            >
              ❌ 未联系
            </button>
          </div>
          <p className="mt-1 text-xs text-gray-500">PhD 录取主要看导师是否愿意要你, 已联系录取率 +15%</p>
        </Field>
      )}

      {/* P4.3 (2026-07-19): 跨专业 / 第二学位 */}
      {visibility.show_cross_disc && (
        <div className="space-y-3 mt-3">
          <Field label="🔄 是否跨专业申请?">
            <div className="flex gap-2">
              <button type="button" onClick={() => update('is_cross_disciplinary', true)}
                className={`flex-1 px-3 py-2 text-sm rounded-lg border transition ${form.is_cross_disciplinary ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-200 hover:border-gray-300 text-gray-700'}`}>
                ✅ 是 (跨专业申请)
              </button>
              <button type="button" onClick={() => update('is_cross_disciplinary', false)}
                className={`flex-1 px-3 py-2 text-sm rounded-lg border transition ${!form.is_cross_disciplinary ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-200 hover:border-gray-300 text-gray-700'}`}>
                ❌ 否 (同/同类专业)
              </button>
            </div>
            {form.is_cross_disciplinary && (
              <div className="mt-2 space-y-2 pl-2 border-l-2 border-amber-200">
                <Field label="✅ 是否补修过先修课 (如算法/数据结构)">
                  <div className="flex gap-2">
                    <button type="button" onClick={() => update('prerequisite_completed', true)}
                      className={`flex-1 px-2 py-1 text-xs rounded border ${form.prerequisite_completed ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-200'}`}>是</button>
                    <button type="button" onClick={() => update('prerequisite_completed', false)}
                      className={`flex-1 px-2 py-1 text-xs rounded border ${!form.prerequisite_completed ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-200'}`}>否</button>
                  </div>
                </Field>
                <Field label="🎓 是否有第二学位 (相关领域)">
                  <div className="flex gap-2">
                    <button type="button" onClick={() => update('has_second_degree', true)}
                      className={`flex-1 px-2 py-1 text-xs rounded border ${form.has_second_degree ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-200'}`}>有</button>
                    <button type="button" onClick={() => update('has_second_degree', false)}
                      className={`flex-1 px-2 py-1 text-xs rounded border ${!form.has_second_degree ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-200'}`}>无</button>
                  </div>
                </Field>
              </div>
            )}
          </Field>
        </div>
      )}

      {/* P3.9-4 (2026-07-18): 推荐信强度 (PhD/master) */}
      {visibility.show_lor && (
        <Field label="📝 推荐信强度 (如有)">
          <div className="grid grid-cols-3 gap-2">
            {[
              { value: 'strong', label: '👍 强推 (知名教授)' },
              { value: 'medium', label: '👌 一般 (普通教授)' },
              { value: 'weak', label: '🤷 弱推 (填表式)' },
            ].map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => update('recommendation_level', opt.value)}
                className={`px-2 py-1.5 text-xs rounded border transition ${
                  form.recommendation_level === opt.value
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-gray-200 hover:border-gray-300 text-gray-700'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <p className="mt-1 text-xs text-gray-500">强推录取率 +10%, 普遍一般, 弱推 -5%</p>
        </Field>
      )}

      {/* 高中生独有: 顶尖夏校 (含金量极高) */}
      {visibility.show_summer_camp && (
        <Field label="顶尖夏校 / 科研项目 (高中生独有)">
          <div className="grid grid-cols-2 gap-2">
            {['RSI 科研夏校 (美)', 'SSP 夏校 (美)', '清华暑校', '北大暑校', '其他顶级夏校', '无'].map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => toggle('summer_camp', v)}
                className={`px-2 py-1.5 text-xs rounded border transition ${
                  (form.summer_camp || []).includes(v)
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-gray-200 hover:border-gray-300 text-gray-700'
                }`}
              >
                {v}
              </button>
            ))}
          </div>
          <p className="mt-1 text-xs text-gray-500"> 顶尖夏校在本科申请中可作为主面试题, 含金量远超一般活动</p>
        </Field>
      )}

      {/* 学科竞赛 (奥赛/AMC) */}
      {visibility.show_olympiad && (
        <Field label="学科竞赛 (多选, 高含金量)">
          <div className="grid grid-cols-2 gap-2">
            {['数学奥赛 (CMO/IMO)', '物理奥赛 (CPhO/IPhO)', '化学奥赛 (CChO)', '生物奥赛 (CBO)', '信息学奥赛 (NOI/IOI)', 'AMC/AIME (美数学)', '其他奥赛', '无'].map((c) => (
              <button
                key={c}
                onClick={() => toggle('competition', c)}
                className={`px-2 py-1.5 text-xs rounded border transition ${
                  (form.competition || []).includes(c)
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-gray-200 hover:border-gray-300 text-gray-700'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        </Field>
      )}

      {/* 商赛/挑战杯 (本科生含金量高) */}
      {stageGroup !== 'high_school' && (
        <Field label="其他竞赛 (商赛/挑战杯等)">
          <div className="grid grid-cols-2 gap-2">
            {['挑战杯/互联网+', '数学建模 (国赛/美赛)', 'ACM/ICPC', '商学院案例大赛', '全国大学生英语竞赛', '其他', '无'].map((c) => (
              <button
                key={c}
                onClick={() => toggle('other_competition', c)}
                className={`px-2 py-1.5 text-xs rounded border transition ${
                  (form.other_competition || []).includes(c)
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-gray-200 hover:border-gray-300 text-gray-700'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        </Field>
      )}

      {/* R48 (R42 P1-2): 课外活动 / 国际交流 */}
      <Field label="课外活动 (学生会/社团/公益/体育等)">
        <div className="grid grid-cols-2 gap-2">
          {[
            '学生会主席/部长',
            '社团创始人',
            '公益/志愿者长期',
            '体育校队',
            '艺术/音乐特长',
            '创业经历',
            '学科外竞赛 (演讲/辩论)',
            '社区服务',
          ].map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => {
                const arr = form.extracurricular || [];
                const next = arr.includes(v)
                  ? arr.filter((x) => x !== v)
                  : [...arr, v];
                update('extracurricular', next as any);
              }}
              className={`px-2 py-1.5 text-xs rounded border transition ${
                (form.extracurricular || []).includes(v)
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-200 hover:border-gray-300 text-gray-700'
              }`}
            >
              {v}
            </button>
          ))}
        </div>
        <p className="mt-1 text-xs text-gray-500">美国 Top30 招生官看重持续性与领导力, 不是数量</p>
      </Field>

      {/* 国际交流 / 海外经历 (高中含金量极高) */}
      <Field label="海外 / 国际交流经历">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.international_exchange || false}
            onChange={(e) => update('international_exchange', e.target.checked)}
            className="w-4 h-4 accent-primary-600"
          />
          有海外短期项目 (夏校/夏令营/交换/国际竞赛)
        </label>
        {form.international_exchange && (
          <label className="flex items-center gap-2 text-sm mt-2 pl-6">
            <input
              type="checkbox"
              checked={form.international_exchange_top || false}
              onChange={(e) => update('international_exchange_top', e.target.checked)}
              className="w-4 h-4 accent-primary-600"
            />
            <span className="font-medium text-amber-700">是否顶尖项目 (RSI / SSP / 清华暑校等)</span>
          </label>
        )}
      </Field>

      {/* 推荐信 (硕博 + 本科申硕) */}
      {visibility.show_lor && (
        <Field label="推荐信准备情况">
          <div className="grid grid-cols-2 gap-2">
            {['2 封推荐信已就绪', '1 封已就绪', '联系中 (老师已同意)', '还没开始', '不需要 (艺术/设计作品集代替)'].map((v) => (
              <button
                key={v}
                onClick={() => update('lor_status', v as any)}
                className={`px-2 py-1.5 text-xs rounded border transition ${
                  form.lor_status === v
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-gray-200 hover:border-gray-300 text-gray-700'
                }`}
              >
                {v}
              </button>
            ))}
          </div>
        </Field>
      )}

      {/* 学生组织/leadership (都有) */}
      <Field label="学生组织 / 领导力">
        <div className="grid grid-cols-2 gap-2">
          {['学生会主席/副主席', '社团负责人', '班长/年级长', '创始社团', '其他', '无'].map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => toggle('student_org', v)}
              className={`px-2 py-1.5 text-xs rounded border transition ${
                (form.student_org || []).includes(v)
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-200 hover:border-gray-300 text-gray-700'
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </Field>

      {/* 志愿者 / 公益 (都有) */}
      <Field label="志愿者 / 公益 (多选)">
        <div className="grid grid-cols-2 gap-2">
          {['国际 NGO (联合国/无国界)', '国内公益', '支教', '环保/动物保护', '其他', '无'].map((v) => (
            <button
              key={v}
              onClick={() => toggle('volunteer', v)}
              className={`px-2 py-1.5 text-xs rounded border transition ${
                (form.volunteer || []).includes(v)
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-200 hover:border-gray-300 text-gray-700'
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </Field>

      {/* 作品集 (艺术/设计/建筑) */}
      {visibility.show_portfolio && (
        <Field label="作品集 (艺术/设计/建筑)">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.portfolio || false}
              onChange={(e) => update('portfolio', e.target.checked)}
              className="w-4 h-4 accent-primary-600"
            />
            我有作品集 (申请艺术/设计/建筑专业)
          </label>
        </Field>
      )}

      {/* R45 (R42 P0-3): MBA 工作年限 / PhD 套磁状态 */}
      {visibility.show_work_years && (
        <Field label={form.target_degree === 'MBA' ? '毕业后工作年限 (MBA 需 ≥ 2-3 年)' : '工作年限'}>
          <input
            type="number"
            min="0"
            value={form.work_years || 0}
            onChange={(e) => update('work_years', parseInt(e.target.value) || 0)}
            placeholder="例: 2 (有 2 年工作经历)"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
          />
        </Field>
      )}

      {visibility.show_contact && (
        <Field label="PhD 套磁状态 (跟潜在导师 email 联系)">
          <select
            value={form.contact_status || 'not_started'}
            onChange={(e) => update('contact_status', e.target.value)}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
          >
            <option value="not_started">还没开始套磁</option>
            <option value="emailed">已发邮件, 未收到回复</option>
            <option value="received_reply">已收到 1-2 位导师回复</option>
            <option value="invited">收到 3+ 导师面试/邀请</option>
            <option value="accepted">已与某导师达成口头 offer</option>
          </select>
          <p className="mt-1 text-xs text-gray-500">PhD 是跟导师"双选", 套磁状态比 GPA 还重要. 收到 1 位面试邀约 = 录取率 80%+</p>
        </Field>
      )}
    </div>
  );
}

// ─── Step 6: 预算 + 偏好 ────────────────────────────────────────
function Step6Budget({ form, update, selectedCountries }: {
  form: MultiStageFormData;
  update: <K extends keyof MultiStageFormData>(k: K, v: MultiStageFormData[K]) => void;
  selectedCountries: CountryMeta[];
}) {
  // 推荐预算区间 (按所选国家)
  const avgBudget = selectedCountries.length === 0 ? 50 :
    Math.round(
      selectedCountries.reduce((sum, c) => {
        // 粗略估算: 美国 60, 英国 50, 加拿大 45, 澳洲 45, 香港 35, 新加坡 45, 日韩 25, 欧洲公立 15
        const map: Record<string, number> = {
          US: 60, UK: 50, CA: 45, AU: 45, HK: 35, SG: 45,
          JP: 25, KR: 25, FR: 15, DE: 15, NL: 25, CH: 40,
          IT: 15, ES: 15, IE: 35, NZ: 40, MY: 20,
        };
        return sum + (map[c.id] || 40);
      }, 0) / selectedCountries.length
    );

  return (
    <div className="space-y-4">
      <h3 className="text-base font-bold text-gray-800 inline-flex items-center gap-2">
        <Wallet className="w-5 h-5 text-primary-600" />
        预算 + 偏好
      </h3>

      {/* R43 (2026-07-17): 预算推荐提示 (学费+生活费 分开显示) */}
      <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 space-y-1">
        <div>💡 按你选的国家, <strong>学费</strong>推荐 <strong>{avgBudget} 万/年</strong> + <strong>生活费</strong> ~12-20 万/年 (城市差异大)</div>
        <div>你填的实际预算: 学费 {form.budget_min}-{form.budget_max} + 生活费 {form.living_min || 0}-{form.living_max || 0} = 总 {(form.budget_min + (form.living_min || 0))}-{(form.budget_max + (form.living_max || 0))} 万/年</div>
      </div>

      {/* R43 (2026-07-17): 预算拆分为 学费 + 生活费 (4 字段), 之前合并不合理 */}
      <div className="text-xs font-semibold text-gray-700">学费 (万/年)</div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="下限">
          <input
            type="number"
            min="0"
            value={form.budget_min || 0}
            onChange={(e) => update('budget_min', parseInt(e.target.value) || 0)}
            placeholder="美本文理 30-50 / 理工 35-55 / 公立研 5-15"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
          />
        </Field>
        <Field label="上限">
          <input
            type="number"
            min="0"
            value={form.budget_max || 0}
            onChange={(e) => update('budget_max', parseInt(e.target.value) || 0)}
            placeholder="美硕 30-70 / 英硕 25-40 / 港新 18-30"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
          />
        </Field>
      </div>

      <div className="text-xs font-semibold text-gray-700 mt-3">生活费 (万/年)</div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="下限">
          <input
            type="number"
            min="0"
            value={form.living_min || 0}
            onChange={(e) => update('living_min', parseInt(e.target.value) || 0)}
            placeholder="大城市 15-25 / 小城市 8-12"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
          />
        </Field>
        <Field label="上限">
          <input
            type="number"
            min="0"
            value={form.living_max || 0}
            onChange={(e) => update('living_max', parseInt(e.target.value) || 0)}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
          />
        </Field>
      </div>

      {/* R44: 资金来源 (P0-2) */}
      <Field label="资金来源 (主要)">
        <select
          value={form.funding_source || 'parents'}
          onChange={(e) => update('funding_source', e.target.value)}
          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg"
        >
          <option value="parents">父母全额支持</option>
          <option value="parents_partial">父母部分 + 自费 / 打工</option>
          <option value="scholarship">主要靠奖学金 (需中服务或高水平)</option>
          <option value="loan">主要靠贷款 (需光重点申高奖学校)</option>
          <option value="self">完全自费 (打工/有存款)</option>
        </select>
      </Field>

      <Field label="是否需要奖学金">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.scholarship_needed || false}
            onChange={(e) => update('scholarship_needed', e.target.checked)}
            className="w-4 h-4 accent-primary-600"
          />
          需要奖学金 (推荐匹配给奖学金额外的学校)
        </label>
      </Field>

      <Field label="地理位置偏好">
        <div className="grid grid-cols-2 gap-2">
          {[
            { v: 'urban', l: '都市' },
            { v: 'suburban', l: '郊区' },
            { v: 'rural', l: '乡村' },
            { v: 'any', l: '不限制' },
          ].map((o) => (
            <button
              key={o.v}
              type="button"
              onClick={() => update('campus_preference', o.v)}
              className={`px-3 py-2 text-xs rounded border ${
                form.campus_preference === o.v
                  ? 'border-primary-500 bg-primary-50 text-primary-700 font-medium'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              {o.l}
            </button>
          ))}
        </div>
      </Field>

      <Field label="学校规模偏好">
        <div className="grid grid-cols-2 gap-2">
          {[
            { v: 'large', l: '大型 (大U 30k+)' },
            { v: 'medium', l: '中型 (10k-30k)' },
            { v: 'small', l: '小型 (文理 <10k)' },
            { v: 'any', l: '不限制' },
          ].map((o) => (
            <button
              key={o.v}
              onClick={() => update('school_size', o.v)}
              className={`px-3 py-2 text-xs rounded border ${
                form.school_size === o.v
                  ? 'border-primary-500 bg-primary-50 text-primary-700 font-medium'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              {o.l}
            </button>
          ))}
        </div>
      </Field>
    </div>
  );
}

// ─── Helper ───────────────────────────────────────────────────────
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-gray-600 mb-1">{label}</label>
      {children}
    </div>
  );
}