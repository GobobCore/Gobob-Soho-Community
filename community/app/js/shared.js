// js/shared.js — Gobob SOHO 共享层：API 封装 + 认证状态 + 工具
window.SohoShared = (function () {
  const TOKEN_KEY = "soho_token";
  const USER_KEY = "soho_user";

  function getToken() { return localStorage.getItem(TOKEN_KEY) || ""; }
  function getUser() {
    try { return JSON.parse(localStorage.getItem(USER_KEY) || "null"); } catch { return null; }
  }
  function setAuth(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }
  function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  async function api(path, opts = {}) {
    // 后端 redirect_slashes=True，POST 不带 / 会 307，浏览器不自动 follow
    // 统一规范化：POST/PUT/DELETE 强制带 /
    let p = path;
    const m = (opts.method || "GET").toUpperCase();
    if (m !== "GET" && p.indexOf("?") === -1 && !p.endsWith("/")) p += "/";
    const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    const tok = getToken();
    if (tok) headers["Authorization"] = "Bearer " + tok;
    let res;
    try {
      res = await fetch(p, { ...opts, headers, redirect: "follow" });
    } catch (e) {
      throw new Error("网络错误：" + e.message);
    }
    if (res.status === 401) { clearAuth(); location.hash = "#/login"; throw new Error("登录已过期"); }
    let data = null;
    try { data = await res.json(); } catch { /* 空响应 */ }
    if (!res.ok) {
      const msg = (data && (data.detail || data.message)) || ("请求失败 " + res.status);
      throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
    return data;
  }
  const get = (p) => api(p);
  const post = (p, body) => api(p, { method: "POST", body: JSON.stringify(body || {}) });
  const put = (p, body) => api(p, { method: "PUT", body: JSON.stringify(body || {}) });

  // 角色判断
  const u = getUser();
  const role = u && u.role;
  const isOwner = role === "owner";
  const isStaff = role === "owner" || role === "advisor";
  const isStudentSide = role === "student" || role === "parent";

  // 常用格式化
  function fmtDate(s) { if (!s) return "—"; return String(s).slice(0, 10); }
  function fmtMoney(n) { if (n == null) return "—"; return "¥" + Number(n).toLocaleString(); }
  const PHASE_LABEL = { overall: "全程", exam: "考试", writing: "文书", school: "选校", interview: "面试", visa: "签证", other: "其他" };
  const LEAD_STATUS_LABEL = { new: "新线索", contacted: "已联系", qualified: "意向确认", proposal: "方案报价", negotiation: "签约谈判", converted: "已签约", lost: "已流失", recycled: "公海" };
  const LOST_REASON_LABEL = { price_too_high: "价格过高", chose_competitor: "选了竞品", decided_not_to_apply: "放弃申请", lost_contact: "联系不上", other: "其他" };
  const APP_STATUS_LABEL = { preparing: "准备中", submitted: "已递交", under_review: "审核中", interview: "面试", offer: "录取", rejection: "拒录", waitlist: "候补" };
  const CONTRACT_STATUS_LABEL = { active: "履约中", completed: "已完成", terminated: "已终止" };

  // R-Design 2026-09-16 v2: 扁平化单色 SVG 图标 (替代 emoji)
  // 参考 lucide-react 的 path 数据, 24x24 viewBox, strokeWidth=1.5, currentColor
  // 用法: <span v-html="$options.ICONS.dashboard"></span> 或 <span v-html="ctx.shared.ICONS.dashboard"></span>
  function svg(paths, extra = "") {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="inline-block w-4 h-4 align-text-bottom" ${extra}>${paths}</svg>`;
  }
  const ICONS = {
    // 工作台导航
    dashboard:    svg('<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>'),
    leads:        svg('<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>'),  // Target
    students:     svg('<path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/>'),  // GraduationCap
    contracts:    svg('<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>'),  // FileText
    staff:        svg('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),  // Users
    collisions:   svg('<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>'),  // Zap
    reports:      svg('<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M7 13l3-3 4 4 5-6"/>'),  // TrendingUp
    settings:     svg('<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>'),  // Settings
    messages:     svg('<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>'),  // MessageCircle
    notifications:svg('<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>'),  // Bell
    myProgress:   svg('<path d="M14.106 5.553a2 2 0 0 0 1.788 0l3.659-1.83A1 1 0 0 1 21 4.619v12.764a1 1 0 0 1-.553.894l-4.553 2.277a2 2 0 0 1-1.788 0l-4.212-2.106a2 2 0 0 0-1.788 0l-3.659 1.83A1 1 0 0 1 3 19.381V6.618a1 1 0 0 1 .553-.894l4.553-2.277a2 2 0 0 1 1.788 0z"/><path d="M15 5.764v15"/><path d="M9 3.236v15"/>'),  // Map
    myTasks:      svg('<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="m9 14 2 2 4-4"/>'),  // ClipboardCheck
    myContract:   svg('<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>'),  // FileText (same as contracts)
    // 状态/装饰
    check:        svg('<path d="M20 6 9 17l-5-5"/>'),
    checkCircle:  svg('<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>'),
    sparkles:     svg('<path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/>'),
    target:       svg('<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>'),
    alert:        svg('<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>'),  // AlertCircle
    gift:         svg('<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13"/><path d="M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7"/><path d="M7.5 8a2.5 2.5 0 0 1 0-5C11 3 12 8 12 8s1-5 4.5-5a2.5 2.5 0 0 1 0 5"/>'),
    logout:       svg('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>'),
  };

  return {
    getToken, getUser, setAuth, clearAuth,
    api, get, post, put,
    isOwner, isStaff, isStudentSide,
    fmtDate, fmtMoney, PHASE_LABEL, LEAD_STATUS_LABEL, LOST_REASON_LABEL, APP_STATUS_LABEL, CONTRACT_STATUS_LABEL,
    ICONS,
  };
})();
