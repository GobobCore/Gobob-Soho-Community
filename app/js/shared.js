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
    const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    const tok = getToken();
    if (tok) headers["Authorization"] = "Bearer " + tok;
    let res;
    try {
      res = await fetch(path, { ...opts, headers });
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
  const LEAD_STATUS_LABEL = { new: "新线索", contacted: "已联系", qualified: "意向确认", proposal: "方案报价", negotiation: "签约谈判", converted: "已签约", lost: "已流失" };
  const APP_STATUS_LABEL = { preparing: "准备中", submitted: "已递交", under_review: "审核中", interview: "面试", offer: "录取", rejection: "拒录", waitlist: "候补" };
  const CONTRACT_STATUS_LABEL = { active: "履约中", completed: "已完成", terminated: "已终止" };

  return {
    getToken, getUser, setAuth, clearAuth,
    api, get, post, put,
    isOwner, isStaff, isStudentSide,
    fmtDate, fmtMoney, PHASE_LABEL, LEAD_STATUS_LABEL, APP_STATUS_LABEL, CONTRACT_STATUS_LABEL,
  };
})();
